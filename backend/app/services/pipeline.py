"""Worker pipeline: re-authorise, preflight, staged execution, ingest, finalize."""

from __future__ import annotations

import logging
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain import RunMode, RunStatus, StageCode, StageState
from app.models import (
    Activity,
    AuditEvent,
    Build,
    Job,
    Observation,
    OpenApiDocument,
    Project,
    ProjectMember,
    Run,
    TargetConfig,
    User,
)
from app.services import demo, ingest, releases

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)
from app.services.evidence import artifact_root
from app.services.findings import coverage_counts
from app.services.policy import PolicyError, TargetPolicy
from app.services.profiles import get_profile
from app.services.queue import finish_job, heartbeat, is_cancel_requested
from app.services.replays import send
from app.services.runs import (
    add_activity,
    finish_stage,
    run_policy,
    start_stage,
)
from app.services.strix_adapter import (
    live_preflight,
    live_result_row,
    normalize_result,
    run_directory,
    run_live,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def probe_build_identity(policy: TargetPolicy, build: Build) -> dict[str, Any]:
    url = build.target_url.rstrip("/") + "/api/meta"
    exchange = send(policy=policy, method="GET", url=url, headers={"Accept": "application/json"})
    observed = ""
    if exchange.status == 200:
        payload = exchange.json()
        if isinstance(payload, dict):
            observed = str(payload.get("build") or payload.get("build_identity") or "")
        if not observed:
            observed = str(exchange.response_headers.get("x-build-identity", ""))
    return {
        "expected": build.expected_identity,
        "observed": observed,
        "status": exchange.status,
        "error": exchange.error or "",
        "matches": bool(observed) and observed == build.expected_identity,
        "at": utcnow().isoformat(),
    }


def reauthorize(db: Session, run: Run) -> tuple[bool, str]:
    """Re-check the requester, project access, and current target policy before dispatch."""
    build = db.get(Build, run.build_id)
    project = db.get(Project, run.project_id)
    if build is None or project is None or build.project_id != project.id:
        return False, "The project or build binding no longer exists."
    requester = db.get(User, run.requested_by) if run.requested_by else None
    if requester is None or not requester.is_active:
        return False, "The requesting account is no longer active."
    if not requester.is_admin:
        member = db.execute(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == requester.id
            )
        ).scalar_one_or_none()
        if member is None:
            return False, "The requester no longer has access to this project."
    config = db.execute(
        select(TargetConfig)
        .where(TargetConfig.project_id == project.id)
        .order_by(TargetConfig.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    if config is None:
        return False, "The project has no approved target policy."
    policy = TargetPolicy.from_config(
        config, allow_loopback=bool(get_settings().allow_loopback_lab_targets)
    )
    try:
        policy.check(build.target_url)
    except PolicyError as exc:
        return False, f"The build destination is no longer inside the approved policy ({exc.code})."
    snapshot = run.scope_snapshot or {}
    if snapshot.get("target_config_id") and str(config.id) != str(snapshot.get("target_config_id")):
        # A newer configuration revision applies; narrowing is enforced above, and the
        # snapshot keeps the historical record of what the requester approved.
        _record(
            db,
            run,
            f"Target policy revision changed before dispatch; re-validated against revision {config.revision}.",
            level="warn",
        )
    return True, ""


def _record(db: Session, run: Run, message: str, *, level: str = "info", code: str = "") -> None:
    add_activity(db, run.id, message, code=code, level=level)
    db.flush()


def _fail(
    db: Session,
    *,
    run: Run,
    job: Job,
    reason: str,
    stage_code: str | None = None,
    error_code: str = "execution_failed",
) -> None:
    run.status = RunStatus.FAILED
    run.failure_reason = reason[:1000]
    run.completed_at = utcnow()
    run.snapshot_at = run.completed_at
    if stage_code:
        finish_stage(db, run.id, stage_code, StageState.FAILED.value, reason)
    finish_job(db, job=job, state="failed", error_code=error_code, error_detail=reason)
    _record(db, run, reason, level="error", code=error_code)
    db.add(
        AuditEvent(
            project_id=run.project_id,
            action="run.failed",
            target_type="run",
            target_id=str(run.id),
            metadata_json={"reason": error_code, "detail": reason[:300]},
        )
    )
    db.flush()


def _cancel(db: Session, *, run: Run, job: Job, detail: str) -> None:
    run.status = RunStatus.CANCELED
    run.failure_reason = detail
    run.completed_at = utcnow()
    run.snapshot_at = run.completed_at
    for code in (StageCode.VERIFY_KNOWN, StageCode.DISCOVERY, StageCode.INGEST, StageCode.FINALIZE):
        from app.services.runs import stage

        row = stage(db, run.id, code.value)
        if row is not None and row.state in {StageState.PENDING.value, StageState.RUNNING.value}:
            finish_stage(db, run.id, code.value, StageState.CANCELED.value, detail)
    finish_job(db, job=job, state="canceled", error_code="canceled")
    _record(db, run, detail, level="warn", code="run.canceled")
    db.add(
        AuditEvent(
            project_id=run.project_id,
            action="run.canceled",
            target_type="run",
            target_id=str(run.id),
            metadata_json={"detail": detail[:300]},
        )
    )
    db.flush()


def _canceled(db: Session, job: Job) -> bool:
    return is_cancel_requested(db, job.id)


def _stale_observations(db: Session, run: Run, reason: str) -> int:
    rows = list(
        db.execute(
            select(Observation).where(Observation.run_id == run.id, Observation.accepted.is_(True))
        ).scalars()
    )
    for row in rows:
        detail = dict(row.detail or {})
        detail["stale"] = True
        detail["stale_reason"] = reason
        row.detail = detail
    db.flush()
    return len(rows)


def execute_run(db: Session, *, run: Run, job: Job, settings: Settings) -> dict[str, Any]:
    if run.status in {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELED,
        RunStatus.INTERRUPTED,
    }:
        finish_job(
            db, job=job, state=job.state if job.state in {"succeeded", "failed"} else "succeeded"
        )
        return {"skipped": True, "reason": "run already terminal"}

    if _canceled(db, job):
        _cancel(db, run=run, job=job, detail="Cancellation was requested before execution started.")
        return {"canceled": True}

    ok, reason = reauthorize(db, run)
    if not ok:
        _fail(
            db,
            run=run,
            job=job,
            reason=reason,
            stage_code=StageCode.PREFLIGHT.value,
            error_code="authorization_revoked",
        )
        return {"failed": True, "reason": reason}

    run.status = RunStatus.RUNNING
    run.started_at = utcnow()
    db.flush()
    _record(db, run, "Execution started by the worker.", code="run.started")
    db.add(
        AuditEvent(
            project_id=run.project_id,
            action="run.started",
            target_type="run",
            target_id=str(run.id),
            metadata_json={"mode": run.mode, "depth": run.depth, "kind": run.kind},
        )
    )
    db.flush()

    build = db.get(Build, run.build_id)
    assert build is not None
    start_stage(db, run.id, StageCode.PREFLIGHT.value)
    heartbeat(db, job=job, settings=settings)

    try:
        policy = run_policy(db, build, settings)
    except Exception as exc:
        _fail(
            db,
            run=run,
            job=job,
            reason="The build has no usable target policy.",
            stage_code=StageCode.PREFLIGHT.value,
            error_code="policy_missing",
        )
        return {"failed": True, "reason": str(exc)}

    identity = probe_build_identity(policy, build)
    snapshot = dict(run.scope_snapshot or {})
    snapshot["identity_checks"] = [{"phase": "pre", **identity}]
    run.scope_snapshot = snapshot
    db.flush()
    if identity["status"] is None:
        _fail(
            db,
            run=run,
            job=job,
            reason=(
                "The approved target could not be reached from the worker. Start the lab or "
                "restore staging connectivity, then retry."
            ),
            stage_code=StageCode.PREFLIGHT.value,
            error_code="target_unreachable",
        )
        return {"failed": True}
    if not identity["matches"]:
        _fail(
            db,
            run=run,
            job=job,
            reason=(
                "The deployed build identity does not match the approved build "
                f"(expected {identity['expected'] or 'unrecorded'}, observed "
                f"{identity['observed'] or 'unavailable'}). Affected results would be inconclusive."
            ),
            stage_code=StageCode.PREFLIGHT.value,
            error_code="build_identity_mismatch",
        )
        return {"failed": True}

    if run.mode == RunMode.LIVE.value:
        pre = live_preflight(settings)
        if not pre.ok:
            _fail(
                db,
                run=run,
                job=job,
                reason="Live execution prerequisites failed: "
                + "; ".join(
                    f"{check['label']} — {check['detail']}"
                    for check in pre.checks
                    if check["status"] == "fail"
                ),
                stage_code=StageCode.PREFLIGHT.value,
                error_code="live_prerequisites_failed",
            )
            return {"failed": True}
        snapshot["live_preflight"] = pre.checks
        run.scope_snapshot = snapshot
    finish_stage(db, run.id, StageCode.PREFLIGHT.value, StageState.DONE.value, "Preflight passed.")
    _record(
        db, run, f"Build identity verified as {identity['observed']}.", code="identity.verified"
    )
    heartbeat(db, job=job, settings=settings)

    deadline = run.started_at.timestamp() + int(run.budget.get("max_runtime_seconds", 3600))

    def expired() -> bool:
        return datetime.now(UTC).timestamp() > deadline

    def cancelled() -> bool:
        return _canceled(db, job)

    if run.kind == "release_scan":
        plan = (run.scope_snapshot or {}).get("release_plan")
        if not plan:
            snapshot = dict(run.scope_snapshot or {})
            snapshot["release_plan"] = releases.build_release_plan(db, run)
            run.scope_snapshot = snapshot
            db.flush()
        start_stage(db, run.id, StageCode.VERIFY_KNOWN.value)
        requester = db.get(User, run.requested_by)
        if requester is None:
            _fail(
                db,
                run=run,
                job=job,
                reason="The requesting account is unavailable, so replay cannot be attributed.",
                stage_code=StageCode.VERIFY_KNOWN.value,
                error_code="requester_missing",
            )
            return {"failed": True}
        result = releases.verify_known(
            db,
            run=run,
            settings=settings,
            requester=requester,
            progress=lambda: heartbeat(db, job=job, settings=settings),
        )
        finish_stage(
            db,
            run.id,
            StageCode.VERIFY_KNOWN.value,
            StageState.DONE.value,
            f"{result['attempted_count']} replay(s), {result['skipped_count']} pending or skipped.",
        )
        _record(
            db,
            run,
            f"Verified known findings: {result['attempted_count']} replay(s) recorded.",
            code="stage.verify_known",
        )
        heartbeat(db, job=job, settings=settings)
        if result.get("shared_failure"):
            _fail(
                db,
                run=run,
                job=job,
                reason=(
                    "A shared prerequisite failed during known-finding verification "
                    f"({result['shared_failure']}). The remaining stages were stopped."
                ),
                stage_code=StageCode.DISCOVERY.value,
                error_code="shared_prerequisite_failed",
            )
            return {"failed": True, "verify": result}
        if cancelled():
            _cancel(db, run=run, job=job, detail="Cancellation requested before discovery.")
            return {"canceled": True}
        allowed, reason = releases.discovery_decision(db, run, result)
        if not allowed:
            finish_stage(db, run.id, StageCode.DISCOVERY.value, StageState.SKIPPED.value, reason)
            _record(db, run, reason, level="warn", code="stage.discovery_skipped")
            db.flush()
            discovery_allowed = False
        else:
            discovery_allowed = True
    else:
        finish_stage(
            db,
            run.id,
            StageCode.VERIFY_KNOWN.value,
            StageState.SKIPPED.value,
            "Baseline assessments do not replay known findings.",
        )
        discovery_allowed = True

    artifacts_dir: Path | None = None
    if discovery_allowed and not cancelled():
        start_stage(db, run.id, StageCode.DISCOVERY.value)
        _record(db, run, "Discovery and bounded active testing started.", code="stage.discovery")
        run_dir = run_directory(artifact_root(), run.id)
        if run.mode == RunMode.DEMO.value:
            target = demo.write_demo_artifacts(
                run_dir,
                build_label=build.label,
                depth=run.depth,
                base_url=build.target_url,
                run_id=str(run.id),
            )
            artifacts_dir = target
            _record(
                db,
                run,
                "Deterministic synthetic demo artifacts were produced by the fixture adapter.",
                code="stage.discovery.demo",
            )
        else:
            spec_path = None
            if build.openapi_document_id:
                document = db.get(OpenApiDocument, build.openapi_document_id)
                if document is not None and document.sanitized_json:
                    import json as _json

                    spec_path = run_dir / "openapi.sanitized.json"
                    spec_path.write_text(
                        _json.dumps(document.sanitized_json, indent=2), encoding="utf-8"
                    )
            profile = get_profile(run.profile_code, run.profile_version)
            result = run_live(
                settings,
                target_url=build.target_url,
                depth=run.depth,
                budget_usd=float(run.budget.get("engine_budget_usd", 1.0)),
                max_turns=int(run.budget.get("engine_max_turns", 20)),
                approved_origins=list((run.scope_snapshot or {}).get("allowed_origins", [])),
                profile_name=profile.name,
                run_dir=run_dir,
                spec_path=spec_path,
                timeout_seconds=int(run.budget.get("max_runtime_seconds", 3600)),
                cancel_check=cancelled,
                heartbeat=lambda: heartbeat(db, job=job, settings=settings),
            )
            normalized = normalize_result(result)
            snapshot = dict(run.scope_snapshot or {})
            snapshot["live_result"] = live_result_row(result)
            run.scope_snapshot = snapshot
            db.flush()
            _record(
                db,
                run,
                "Engine process finished: "
                f"exit {result.exit_code}, status {result.raw_status or 'unknown'}.",
                code="stage.discovery.engine",
            )
            if normalized["limitations"]:
                run.limitations = [*(run.limitations or []), *normalized["limitations"]]
            if normalized["status"] == "canceled":
                _cancel(db, run=run, job=job, detail=normalized["reason"])
                return {"canceled": True}
            if normalized["status"] in {"failed", "interrupted"}:
                finish_stage(
                    db,
                    run.id,
                    StageCode.DISCOVERY.value,
                    StageState.FAILED.value,
                    normalized["reason"],
                )
                partial_dir = Path(result.artifacts_dir) if result.artifacts_dir else None
                if partial_dir is not None and partial_dir.exists():
                    bundle = ingest.load_artifact_bundle(partial_dir)
                    if bundle.status != "missing":
                        ingest.ingest_run(
                            db,
                            run=run,
                            project=db.get(Project, run.project_id),
                            build=build,
                            bundle=bundle,
                            limitations=normalized["limitations"],
                        )
                        run.ingest_state = f"partial:{bundle.status}"
                _fail(
                    db,
                    run=run,
                    job=job,
                    reason=normalized["reason"],
                    stage_code=StageCode.DISCOVERY.value,
                    error_code=(
                        "cleanup_unconfirmed" if not result.cleanup_confirmed else "engine_failed"
                    ),
                )
                return {"failed": True}
            artifacts_dir = Path(result.artifacts_dir) if result.artifacts_dir else None
        if artifacts_dir is not None:
            finish_stage(
                db,
                run.id,
                StageCode.DISCOVERY.value,
                StageState.DONE.value,
                "Discovery artifacts collected.",
            )
        else:
            finish_stage(
                db,
                run.id,
                StageCode.DISCOVERY.value,
                StageState.FAILED.value,
                "The engine produced no artifacts.",
            )
    elif not discovery_allowed:
        pass
    else:
        _cancel(db, run=run, job=job, detail="Cancellation requested before discovery.")
        return {"canceled": True}

    heartbeat(db, job=job, settings=settings)
    if cancelled():
        _cancel(db, run=run, job=job, detail="Cancellation requested before artifact ingestion.")
        return {"canceled": True}
    if expired():
        run.status = RunStatus.INTERRUPTED
        run.failure_reason = "The run exceeded its execution deadline during discovery."
        run.completed_at = utcnow()
        run.snapshot_at = run.completed_at
        finish_stage(
            db, run.id, StageCode.INGEST.value, StageState.FAILED.value, run.failure_reason
        )
        finish_job(db, job=job, state="interrupted", error_code="deadline_exceeded")
        _record(db, run, run.failure_reason, level="error", code="deadline_exceeded")
        db.flush()
        return {"interrupted": True}

    start_stage(db, run.id, StageCode.INGEST.value)
    limitations: list[str] = []
    bundle = ingest.ArtifactBundle()
    if artifacts_dir is not None:
        bundle = ingest.load_artifact_bundle(artifacts_dir)
        if run.mode == RunMode.DEMO.value:
            limitations.append(
                "Demo mode: findings and coverage come from deterministic synthetic Strix "
                "artifacts. Automatic retests execute real requests against the bundled lab."
            )
    else:
        limitations.append("No artifact directory was available for ingestion.")
    try:
        summary = ingest.ingest_run(
            db,
            run=run,
            project=db.get(Project, run.project_id),
            build=build,
            bundle=bundle,
            limitations=limitations,
        )
        finish_stage(
            db,
            run.id,
            StageCode.INGEST.value,
            StageState.DONE.value,
            f"{summary.get('imported', 0)} finding record(s) imported from {bundle.status} artifacts.",
        )
    except Exception as exc:
        logger.exception("artifact import failed for run %s", run.id)
        finish_stage(
            db,
            run.id,
            StageCode.INGEST.value,
            StageState.FAILED.value,
            "Artifact import failed; the run retains any partial records already imported.",
        )
        run.ingest_state = "failed"
        run.limitations = [
            *(run.limitations or []),
            "Artifact import failed. Existing records are partial and must not be read as a "
            "complete account of the scan.",
        ]
        _fail(
            db,
            run=run,
            job=job,
            reason="Artifact import failed. Partial results remain viewable.",
            error_code="ingest_failed",
        )
        return {"failed": True, "error": exc.__class__.__name__}

    heartbeat(db, job=job, settings=settings)
    start_stage(db, run.id, StageCode.FINALIZE.value)
    post_identity = probe_build_identity(policy, build)
    snapshot = dict(run.scope_snapshot or {})
    checks = list(snapshot.get("identity_checks") or [])
    checks.append({"phase": "post", **post_identity})
    snapshot["identity_checks"] = checks
    run.scope_snapshot = snapshot
    if not post_identity["matches"]:
        stale_reason = (
            "The deployed build identity changed while the run executed; verification is stale."
        )
        marked = _stale_observations(db, run, stale_reason)
        run.limitations = [*(run.limitations or []), stale_reason]
        run.coverage_complete = False
        _record(db, run, f"{stale_reason} ({marked} observation(s) marked stale).", level="error")

    run.completed_at = utcnow()
    run.snapshot_at = run.completed_at
    run.status = RunStatus.COMPLETED
    run.coverage_complete = run.coverage_complete and bool(
        (bundle.coverage or {}).get("completeness", {}).get("complete")
    )
    report_counts = coverage_counts(db, run)
    _record(
        db,
        run,
        "Run completed: "
        f"{report_counts['counts'].get('finding_observed', 0)} finding check(s), "
        f"{report_counts['counts'].get('not_run', 0)} not run.",
        code="run.completed",
    )
    finish_stage(
        db,
        run.id,
        StageCode.FINALIZE.value,
        StageState.DONE.value,
        "Snapshot recorded."
        if run.coverage_complete
        else "Snapshot recorded with incomplete coverage.",
    )
    finish_job(db, job=job, state="succeeded")
    db.add(
        AuditEvent(
            project_id=run.project_id,
            action="run.completed",
            target_type="run",
            target_id=str(run.id),
            metadata_json={
                "coverage_complete": run.coverage_complete,
                "ingest_state": run.ingest_state,
                "mode": run.mode,
            },
        )
    )
    db.flush()
    return {
        "completed": True,
        "coverage_complete": run.coverage_complete,
        "ingest_state": run.ingest_state,
    }


def run_retest_job(db: Session, *, job: Job, settings: Settings) -> dict[str, Any]:
    from app.models import RetestAttempt
    from app.services.retests import execute_attempt

    attempt_id = (job.payload or {}).get("attempt_id")
    if not attempt_id:
        finish_job(db, job=job, state="failed", error_code="missing_payload")
        return {"failed": True}
    attempt = db.get(RetestAttempt, uuid.UUID(str(attempt_id)))
    if attempt is None:
        finish_job(db, job=job, state="failed", error_code="attempt_missing")
        return {"failed": True}
    execute_attempt(db, attempt=attempt, settings=settings)
    finish_job(db, job=job, state="succeeded")
    db.add(
        AuditEvent(
            project_id=attempt.project_id,
            action="retest.completed",
            target_type="retest_attempt",
            target_id=str(attempt.id),
            metadata_json={"outcome": attempt.outcome, "reason": attempt.reason_code},
        )
    )
    db.flush()
    return {"attempt": str(attempt.id), "outcome": attempt.outcome}


def run_job(db: Session, *, job: Job, settings: Settings) -> dict[str, Any]:
    if job.kind == "retest":
        return run_retest_job(db, job=job, settings=settings)
    run_id = (job.payload or {}).get("run_id")
    if not run_id:
        finish_job(db, job=job, state="failed", error_code="missing_payload")
        return {"failed": True}
    run = db.get(Run, uuid.UUID(str(run_id)))
    if run is None:
        finish_job(db, job=job, state="failed", error_code="run_missing")
        return {"failed": True}
    return execute_run(db, run=run, job=job, settings=settings)


_ = (Activity, ProjectMember)
