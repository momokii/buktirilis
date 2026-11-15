"""Run creation, preflight, scope snapshots, stage tracking, and cancellation."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import (
    TERMINAL_RUN_STATES,
    Depth,
    RunKind,
    RunMode,
    RunStatus,
    StageCode,
    StageState,
)
from app.models import (
    Activity,
    AuditEvent,
    Build,
    Job,
    OpenApiDocument,
    Project,
    ProjectMember,
    Run,
    RunStage,
    TargetConfig,
    TestAccount,
    User,
    utcnow,
)
from app.services.findings import latest_observation
from app.services.policy import PolicyError, TargetPolicy
from app.services.profiles import (
    depth_config,
    get_profile,
    plan_coverage,
    profile_as_json,
)

DEFAULT_RUN_LIMITS = {
    "max_depth": "standard",
    "max_runs_per_day": 8,
    "max_budget_usd": 5.0,
    "max_runtime_seconds": 3600,
    "max_replay_checks": 20,
}


@dataclass
class PreflightCheck:
    code: str
    label: str
    status: str  # pass | fail | warn
    detail: str = ""
    recovery: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "recovery": self.recovery,
        }


@dataclass
class PreflightResult:
    checks: list[PreflightCheck] = field(default_factory=list)
    blocked_scenarios: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(check.status == "fail" for check in self.checks)

    @property
    def requires_reduced_scope_ack(self) -> bool:
        return bool(self.blocked_scenarios)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [check.as_dict() for check in self.checks],
            "blocked_scenarios": self.blocked_scenarios,
            "requires_reduced_scope_ack": self.requires_reduced_scope_ack,
        }

    def failure_detail(self) -> str:
        failed = [c for c in self.checks if c.status == "fail"]
        if not failed:
            return ""
        return "; ".join(f"{c.label}: {c.detail or c.recovery}" for c in failed)


def _project_limits(config: TargetConfig | None) -> dict[str, Any]:
    limits = dict(DEFAULT_RUN_LIMITS)
    if config is not None:
        stored = config.run_limits or {}
        for key, value in stored.items():
            if key in limits and value is not None:
                limits[key] = value
    return limits


def _limits_for_depth(project_limits: dict[str, Any], depth: str) -> dict[str, Any]:
    depth_limits = depth_config(depth)
    max_depth = str(project_limits.get("max_depth", "standard"))
    order = {"quick": 0, "standard": 1, "deep": 2}
    if order.get(depth, 9) > order.get(max_depth, 1):
        raise HTTPException(
            status_code=422,
            detail=f"This project caps assessment depth at {max_depth}",
        )
    replay_budget = int(project_limits.get("max_replay_checks", 20))
    return {
        "depth": depth,
        "max_checks": min(int(depth_limits["max_checks"]), replay_budget),
        "time_budget_seconds": int(depth_limits["time_budget_seconds"]),
        "engine_budget_usd": min(
            float(depth_limits["strix_budget_usd"]),
            float(project_limits.get("max_budget_usd", 5.0)),
        ),
        "engine_max_turns": int(depth_limits["strix_max_turns"]),
        "discovery_share": float(depth_limits["discovery_share"]),
        "max_runtime_seconds": int(project_limits.get("max_runtime_seconds", 3600)),
        "max_replay_checks": replay_budget,
        "estimated_cost_note": (
            "Engine spend is an estimate and can overshoot the configured cap."
        ),
    }


def surface_inventory(db: Session, build: Build, profile_code: str, version: int) -> list[dict]:
    surfaces: list[dict] = []
    if build.openapi_document_id:
        document = db.get(OpenApiDocument, build.openapi_document_id)
        if document is not None:
            for operation in document.operations or []:
                surfaces.append(
                    {
                        "route": operation["path"],
                        "methods": [operation["method"]],
                        "source": "openapi",
                    }
                )
    if not surfaces:
        profile = get_profile(profile_code, version)
        for scenario in profile.scenarios:
            for route in scenario.surfaces:
                surfaces.append({"route": route, "methods": ["GET"], "source": "profile"})
    return surfaces


def run_policy(db: Session, build: Build, settings: Settings) -> TargetPolicy:
    config = db.get(TargetConfig, build.target_config_id)
    if config is None:
        raise HTTPException(status_code=409, detail="Build has no recorded target configuration")
    return TargetPolicy.from_config(
        config, allow_loopback=bool(settings.allow_loopback_lab_targets)
    )


def current_policy(db: Session, project_id: uuid.UUID, settings: Settings) -> TargetPolicy:
    """The latest policy revision, used whenever work is dispatched or re-authorized."""
    config = db.execute(
        select(TargetConfig)
        .where(TargetConfig.project_id == project_id)
        .order_by(TargetConfig.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=409, detail="Project has no approved target policy")
    return TargetPolicy.from_config(
        config, allow_loopback=bool(settings.allow_loopback_lab_targets)
    )


def daily_run_count(db: Session, project_id: uuid.UUID) -> int:
    since = datetime.now(UTC) - timedelta(hours=24)
    return int(
        db.execute(
            select(func.count())
            .select_from(Run)
            .where(Run.project_id == project_id, Run.created_at >= since)
        ).scalar_one()
    )


def preflight(
    db: Session,
    *,
    settings: Settings,
    project: Project,
    build: Build,
    kind: str,
    depth: str,
    profile_code: str,
    profile_version: int,
    account_ids: list[uuid.UUID],
    unauthenticated: bool,
    baseline_run_id: uuid.UUID | None,
) -> PreflightResult:
    result = PreflightResult()
    profile = get_profile(profile_code, profile_version)
    config = db.get(TargetConfig, build.target_config_id)
    limits = _project_limits(config)

    result.checks.append(
        PreflightCheck(
            code="build_binding",
            label="Build belongs to this project",
            status="pass" if build.project_id == project.id else "fail",
            detail=f"{build.label} → {build.target_url}",
            recovery="Register the build under this project before requesting a run.",
        )
    )

    policy = None
    try:
        policy = run_policy(db, build, settings)
        policy.check(build.target_url)
        result.checks.append(
            PreflightCheck(
                code="target_policy",
                label="Approved destination",
                status="pass",
                detail=f"{build.target_url} is inside the approved origin allowlist",
            )
        )
    except (HTTPException, PolicyError) as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        result.checks.append(
            PreflightCheck(
                code="target_policy",
                label="Approved destination",
                status="fail",
                detail=str(detail),
                recovery="Update the project target policy or register a build inside it.",
            )
        )

    if build.openapi_document_id:
        document = db.get(OpenApiDocument, build.openapi_document_id)
        ok = document is not None and document.project_id == project.id
        result.checks.append(
            PreflightCheck(
                code="openapi",
                label="OpenAPI revision",
                status="pass" if ok else "fail",
                detail=(document.filename if document else "referenced revision is missing"),
                recovery="Re-upload the OpenAPI document for this build.",
            )
        )

    identity_ok = bool(build.expected_identity)
    result.checks.append(
        PreflightCheck(
            code="build_identity",
            label="Expected build identity recorded",
            status="pass" if identity_ok else "fail",
            detail=(
                f"expected {build.expected_identity}"
                + (" (operator-attested)" if build.identity_attested_by else " (observed)")
                if identity_ok
                else "No deployed build identity is recorded for this build."
            ),
            recovery="Attest the deployed build identity or record an observed identity first.",
        )
    )

    try:
        _limits_for_depth(limits, depth)
        result.checks.append(
            PreflightCheck(
                code="depth_limits",
                label="Depth and budget limits",
                status="pass",
                detail=f"{depth} within project cap {limits.get('max_depth')}",
            )
        )
    except HTTPException as exc:
        result.checks.append(
            PreflightCheck(
                code="depth_limits",
                label="Depth and budget limits",
                status="fail",
                detail=str(exc.detail),
                recovery="Select a depth allowed by the project's execution settings.",
            )
        )

    runs_today = daily_run_count(db, project.id)
    if runs_today >= int(limits.get("max_runs_per_day", 8)):
        result.checks.append(
            PreflightCheck(
                code="daily_quota",
                label="Daily run quota",
                status="fail",
                detail=f"{runs_today} runs in the last 24 hours",
                recovery="Wait for the quota window to reset or raise the project limit.",
            )
        )
    else:
        result.checks.append(
            PreflightCheck(
                code="daily_quota",
                label="Daily run quota",
                status="pass",
                detail=f"{runs_today} of {limits.get('max_runs_per_day', 8)} used in 24h",
            )
        )

    accounts = (
        list(
            db.execute(
                select(TestAccount).where(
                    TestAccount.project_id == project.id, TestAccount.id.in_(account_ids)
                )
            ).scalars()
        )
        if account_ids
        else []
    )
    if len(accounts) != len(set(account_ids)):
        result.checks.append(
            PreflightCheck(
                code="test_accounts",
                label="Selected test identities",
                status="fail",
                detail="One or more selected identities are not configured for this project.",
                recovery="Pick identities from this project's configuration.",
            )
        )
    required = profile.required_identities
    if unauthenticated:
        result.checks.append(
            PreflightCheck(
                code="test_accounts",
                label="Authentication mode",
                status="pass",
                detail="Deliberate unauthenticated run",
            )
        )
        result.blocked_scenarios = [
            {
                "code": scenario.code,
                "title": scenario.title,
                "reason": "Requires authenticated identities; the operator selected an unauthenticated run.",
            }
            for scenario in profile.scenarios
            if scenario.required_identities >= 1
        ]
        result.checks.append(
            PreflightCheck(
                code="scenario_scope",
                label="Scenario coverage",
                status="warn",
                detail=f"{len(result.blocked_scenarios)} scenarios blocked by unauthenticated scope",
                recovery="Confirm reduced scope or select authenticated identities.",
            )
        )
    elif len(accounts) < required:
        result.checks.append(
            PreflightCheck(
                code="test_accounts",
                label="Required test identities",
                status="warn",
                detail=f"{len(accounts)} selected; profile requires {required} distinct identities",
                recovery="Add the missing test identity and re-run preflight.",
            )
        )
        result.blocked_scenarios = [
            {
                "code": scenario.code,
                "title": scenario.title,
                "reason": f"Needs {scenario.required_identities} distinct authenticated identities.",
            }
            for scenario in profile.scenarios
            if scenario.required_identities > len(accounts)
        ]
    else:
        result.checks.append(
            PreflightCheck(
                code="test_accounts",
                label="Required test identities",
                status="pass",
                detail=f"{len(accounts)} distinct identities selected",
            )
        )

    if kind == RunKind.RELEASE_SCAN:
        baseline = db.get(Run, baseline_run_id) if baseline_run_id else None
        if baseline is None:
            result.checks.append(
                PreflightCheck(
                    code="baseline",
                    label="Comparison baseline",
                    status="fail",
                    detail="A release scan needs an earlier completed run to compare against.",
                    recovery="Complete a baseline assessment or select a completed run.",
                )
            )
        elif baseline.project_id != project.id:
            result.checks.append(
                PreflightCheck(
                    code="baseline",
                    label="Comparison baseline",
                    status="fail",
                    detail="The selected baseline belongs to another project.",
                    recovery="Select a completed run in this project.",
                )
            )
        elif baseline.status != RunStatus.COMPLETED:
            result.checks.append(
                PreflightCheck(
                    code="baseline",
                    label="Comparison baseline",
                    status="fail",
                    detail=f"The selected baseline is {baseline.status}.",
                    recovery="Wait for it to finish or select a completed run.",
                )
            )
        else:
            result.checks.append(
                PreflightCheck(
                    code="baseline",
                    label="Comparison baseline",
                    status="pass",
                    detail=f"Comparing against {baseline.id} on build {baseline.build_id}",
                )
            )
    else:
        if kind != RunKind.BASELINE:
            result.checks.append(
                PreflightCheck(
                    code="kind",
                    label="Run kind",
                    status="fail",
                    detail="Unknown run kind",
                )
            )
        else:
            result.checks.append(
                PreflightCheck(
                    code="kind",
                    label="First assessment type",
                    status="pass",
                    detail="Baseline assessment",
                )
            )

    result.checks.append(
        PreflightCheck(
            code="mode",
            label="Execution mode",
            status="pass",
            detail=(
                "Demo mode: deterministic Strix artifacts with a real constrained replay "
                "against the local lab."
                if settings.demo_enabled
                else "Live mode: the self-hosted Strix CLI is invoked by the worker."
            ),
        )
    )
    if not settings.demo_enabled and not settings.live_enabled:
        result.checks.append(
            PreflightCheck(
                code="live_config",
                label="Live execution configuration",
                status="fail",
                detail="Live mode is not provisioned (missing engine switch or model configuration).",
                recovery="Configure the approved provider/model and enable live execution.",
            )
        )
    return result


def scope_snapshot(
    db: Session,
    *,
    settings: Settings,
    build: Build,
    kind: str,
    depth: str,
    profile_code: str,
    profile_version: int,
    accounts: list[TestAccount],
    unauthenticated: bool,
    baseline_run_id: uuid.UUID | None,
) -> dict[str, Any]:
    config = db.get(TargetConfig, build.target_config_id)
    policy = (
        TargetPolicy.from_config(config, allow_loopback=bool(settings.allow_loopback_lab_targets))
        if config
        else None
    )
    profile = get_profile(profile_code, profile_version)
    surfaces = surface_inventory(db, build, profile_code, profile_version)
    limits = _limits_for_depth(_project_limits(config), depth)
    return {
        "base_url": build.target_url,
        "origins_signature": policy.origins_signature() if policy else "",
        "path_prefixes": list(policy.path_prefixes) if policy else [],
        "allowed_origins": list(policy.allowed_origins) if policy else [],
        "environment_label": policy.environment_label if policy else "",
        "target_config_revision": config.revision if config else None,
        "target_config_id": str(config.id) if config else None,
        "build_label": build.label,
        "build_identity": build.expected_identity,
        "build_identity_source": (
            "operator_attested"
            if build.identity_attested_by and not build.identity_observed
            else "observed"
            if build.identity_observed
            else "unrecorded"
        ),
        "kind": kind,
        "depth": depth,
        "mode": RunMode.DEMO.value if settings.demo_enabled else RunMode.LIVE.value,
        "profile": {"code": profile.code, "version": profile.version, "name": profile.name},
        "profile_config": profile_as_json(profile),
        "accounts": [
            {"name": account.name, "role": account.role_label, "tenant": account.tenant_label}
            for account in accounts
        ],
        "unauthenticated": unauthenticated,
        "surfaces": sorted({surface["route"] for surface in surfaces}),
        "surface_inventory": surfaces,
        "limits": limits,
        "content_limits": {
            "max_artifact_bytes": settings.max_artifact_bytes,
            "max_openapi_bytes": settings.max_openapi_bytes,
        },
        "baseline_run_id": str(baseline_run_id) if baseline_run_id else None,
        "planned_checks": plan_coverage(profile, surfaces=surfaces, depth=depth),
        "approval": {
            "scope_owner": config.scope_owner if config else "",
            "authorization_reference": config.authorization_reference if config else "",
        },
    }


def create_run(
    db: Session,
    *,
    settings: Settings,
    project: Project,
    build: Build,
    kind: str,
    depth: str,
    profile_code: str,
    profile_version: int,
    account_ids: list[uuid.UUID],
    unauthenticated: bool,
    baseline_run_id: uuid.UUID | None,
    actor: User,
    accept_reduced_scope: bool,
) -> tuple[Run, bool]:
    """Create a queued run. Returns ``(run, created)`` for idempotent submissions."""
    pre = preflight(
        db,
        settings=settings,
        project=project,
        build=build,
        kind=kind,
        depth=depth,
        profile_code=profile_code,
        profile_version=profile_version,
        account_ids=account_ids,
        unauthenticated=unauthenticated,
        baseline_run_id=baseline_run_id,
    )
    if not pre.ok:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Preflight failed",
                "checks": [check.as_dict() for check in pre.checks],
                "blocked_scenarios": pre.blocked_scenarios,
            },
        )
    if pre.requires_reduced_scope_ack and not accept_reduced_scope:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Required authenticated prerequisites are incomplete. Confirm reduced "
                    "scope explicitly to continue."
                ),
                "checks": [check.as_dict() for check in pre.checks],
                "blocked_scenarios": pre.blocked_scenarios,
                "requires_reduced_scope_ack": True,
            },
        )

    mode = RunMode.DEMO.value if settings.demo_enabled else RunMode.LIVE.value
    key_payload = {
        "project": str(project.id),
        "build": str(build.id),
        "kind": kind,
        "depth": depth,
        "profile": f"{profile_code}:{profile_version}",
        "accounts": sorted(str(a) for a in account_ids),
        "unauthenticated": unauthenticated,
        "baseline": str(baseline_run_id) if baseline_run_id else None,
        "mode": mode,
    }
    idempotency_key = (
        "run:" + hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()[:40]
    )

    existing = db.execute(
        select(Job, Run)
        .join(Run, Run.job_id == Job.id)
        .where(
            Job.idempotency_key == idempotency_key,
            Job.state.in_(["queued", "running", "cancel_requested"]),
        )
    ).first()
    if existing is not None:
        return existing[1], False

    accounts = (
        list(
            db.execute(
                select(TestAccount).where(
                    TestAccount.project_id == project.id, TestAccount.id.in_(account_ids)
                )
            ).scalars()
        )
        if account_ids
        else []
    )
    snapshot = scope_snapshot(
        db,
        settings=settings,
        build=build,
        kind=kind,
        depth=depth,
        profile_code=profile_code,
        profile_version=profile_version,
        accounts=accounts,
        unauthenticated=unauthenticated,
        baseline_run_id=baseline_run_id,
    )
    run = Run(
        project_id=project.id,
        build_id=build.id,
        baseline_run_id=baseline_run_id,
        kind=kind,
        mode=mode,
        depth=depth,
        profile_code=profile_code,
        profile_version=profile_version,
        status=RunStatus.QUEUED,
        engine="strix",
        engine_version=settings.strix_version if mode == RunMode.LIVE.value else "demo-fixture",
        runtime_image="",
        config_revision_id=build.target_config_id,
        scope_snapshot=snapshot,
        budget=snapshot["limits"],
        requested_by=actor.id,
        requested_by_label=actor.display_name or actor.email,
    )
    db.add(run)
    db.flush()
    if kind == RunKind.RELEASE_SCAN:
        from app.services.releases import build_release_plan

        snapshot["release_plan"] = build_release_plan(db, run)
        run.scope_snapshot = snapshot
        db.flush()
    job = Job(
        project_id=project.id,
        run_id=run.id,
        kind="scan",
        payload={
            "run_id": str(run.id),
            "mode": mode,
            "unauthenticated": unauthenticated,
            "account_ids": [str(a) for a in account_ids],
        },
        state="queued",
        requested_by=actor.id,
        idempotency_key=idempotency_key,
        max_attempts=settings.job_max_attempts,
    )
    db.add(job)
    db.flush()
    run.job_id = job.id
    for code in (
        StageCode.PREFLIGHT,
        StageCode.VERIFY_KNOWN,
        StageCode.DISCOVERY,
        StageCode.INGEST,
        StageCode.FINALIZE,
    ):
        db.add(RunStage(run_id=run.id, code=code.value, state=StageState.PENDING.value))
    db.add(
        Activity(
            run_id=run.id,
            code="run.queued",
            message=f"{kind.replace('_', ' ')} queued by {actor.display_name or actor.email}",
            data={"depth": depth, "mode": mode, "accounts": [a.name for a in accounts]},
        )
    )
    db.add(
        AuditEvent(
            actor_id=actor.id,
            actor_label=actor.display_name or actor.email,
            project_id=project.id,
            action="run.requested",
            target_type="run",
            target_id=str(run.id),
            metadata_json={
                "kind": kind,
                "depth": depth,
                "mode": mode,
                "build": build.label,
                "unauthenticated": unauthenticated,
                "accept_reduced_scope": accept_reduced_scope,
            },
        )
    )
    db.flush()
    return run, True


def cancel_run(db: Session, *, run: Run, actor: User, reason: str = "") -> Run:
    if run.status in TERMINAL_RUN_STATES:
        raise HTTPException(status_code=409, detail=f"This run already finished as {run.status}")
    now = datetime.now(UTC)
    job = db.get(Job, run.job_id) if run.job_id else None
    # A queued job has no worker to observe a cancel request. Finalize it immediately;
    # only a claimed/running job needs the cooperative boundary check.
    if job is None or job.state == "queued":
        run.status = RunStatus.CANCELED
        run.canceled_at = now
        run.completed_at = now
        run.snapshot_at = now
        run.failure_reason = "Canceled before execution started."
        if job is not None:
            job.state = "canceled"
            job.finished_at = now
            job.error_code = "canceled"
        for stage_row in db.execute(
            select(RunStage).where(
                RunStage.run_id == run.id,
                RunStage.state.in_([StageState.PENDING.value, StageState.RUNNING.value]),
            )
        ).scalars():
            stage_row.state = StageState.CANCELED.value
            stage_row.finished_at = now
            stage_row.detail = "Canceled before execution started."
        message = f"Canceled by {actor.display_name or actor.email} before execution started."
    else:
        run.status = RunStatus.CANCEL_REQUESTED
        run.canceled_at = now
        if job.state == "running":
            job.state = "cancel_requested"
        message = f"Cancellation requested by {actor.display_name or actor.email}"
    db.add(
        Activity(
            run_id=run.id,
            code="run.cancel_requested",
            level="warn",
            message=message,
            data={"reason": reason[:300]},
        )
    )
    db.add(
        AuditEvent(
            actor_id=actor.id,
            actor_label=actor.display_name or actor.email,
            project_id=run.project_id,
            action="run.cancel_requested",
            target_type="run",
            target_id=str(run.id),
            metadata_json={"reason": reason[:300]},
        )
    )
    return run


def add_activity(
    db: Session,
    run_id: uuid.UUID,
    message: str,
    *,
    code: str = "",
    level: str = "info",
    data: dict | None = None,
) -> None:
    db.add(
        Activity(
            run_id=run_id,
            code=code,
            level=level,
            message=message[:1000],
            data=data or {},
        )
    )


def stage(db: Session, run_id: uuid.UUID, code: str) -> RunStage | None:
    return db.execute(
        select(RunStage).where(RunStage.run_id == run_id, RunStage.code == code)
    ).scalar_one_or_none()


def start_stage(db: Session, run_id: uuid.UUID, code: str) -> RunStage:
    row = stage(db, run_id, code)
    if row is None:
        row = RunStage(run_id=run_id, code=code)
        db.add(row)
    row.state = StageState.RUNNING.value
    row.started_at = datetime.now(UTC)
    row.detail = ""
    db.flush()
    return row


def finish_stage(db: Session, run_id: uuid.UUID, code: str, state: str, detail: str = "") -> None:
    row = stage(db, run_id, code)
    if row is None:
        row = RunStage(run_id=run_id, code=code)
        db.add(row)
    row.state = state
    row.finished_at = datetime.now(UTC)
    if detail:
        row.detail = detail[:1000]
    db.flush()


def run_progress(db: Session, run: Run) -> dict[str, Any]:
    stages = list(
        db.execute(
            select(RunStage)
            .where(RunStage.run_id == run.id)
            .order_by(RunStage.started_at.nulls_first())
        ).scalars()
    )
    activities = list(
        db.execute(
            select(Activity).where(Activity.run_id == run.id).order_by(Activity.at.desc()).limit(40)
        ).scalars()
    )
    order = ["preflight", "verify_known", "discovery", "ingest", "finalize"]
    stages.sort(key=lambda s: order.index(s.code) if s.code in order else 99)
    return {
        "run_id": str(run.id),
        "status": run.status,
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "elapsed_seconds": (
            int(((run.completed_at or datetime.now(UTC)) - run.started_at).total_seconds())
            if run.started_at
            else None
        ),
        "stages": [
            {
                "code": row.code,
                "state": row.state,
                "detail": row.detail,
                "started_at": _iso(row.started_at),
                "finished_at": _iso(row.finished_at),
            }
            for row in stages
        ],
        "activities": [
            {
                "at": _iso(row.at),
                "level": row.level,
                "code": row.code,
                "message": row.message,
            }
            for row in activities
        ],
        "mode": run.mode,
        "failure_reason": run.failure_reason,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def run_visible_to(db: Session, run: Run, user: User) -> bool:
    if user.is_admin:
        return True
    membership = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == run.project_id, ProjectMember.user_id == user.id
        )
    ).scalar_one_or_none()
    return membership is not None


def display_status(run: Run) -> str:
    if run.status != RunStatus.RUNNING:
        return run.status
    return "running"


def verification_on_build(db: Session, run: Run, finding_id: uuid.UUID) -> Any:
    return latest_observation(db, finding_id, run.build_id)


_ = (utcnow, Depth)
