"""Release Scan planning and staged execution.

Stage 1 replays eligible known findings within an explicit allocation; stage 2 spends
what is left on discovery and bounded active testing. A shared prerequisite failure
(target authorization, build identity) stops the remaining stages.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import (
    SEVERITY_ORDER,
    CoverageResult,
    InconclusiveReason,
    ObservationOutcome,
    RetestMethod,
    Severity,
    VerificationOutcome,
)
from app.models import Build, Finding, OpenApiDocument, Project, Run, RunCheck, User
from app.services.findings import (
    approved_recipe,
    build_run_view,
    eligibility,
    latest_observation,
    state_for_build,
)
from app.services.retests import execute_attempt, queue_automatic_attempt

SHARED_FAILURE_REASONS = {
    InconclusiveReason.BUILD_IDENTITY_MISMATCH.value,
    InconclusiveReason.BUILD_IDENTITY_UNVERIFIED.value,
    InconclusiveReason.SCOPE_DENIED.value,
}


def openapi_operations(db: Session, build: Build) -> dict[str, dict[str, Any]]:
    if not build.openapi_document_id:
        return {}
    document = db.get(OpenApiDocument, build.openapi_document_id)
    if document is None:
        return {}
    return {
        f"{operation.get('method', '').upper()} {operation.get('path', '')}".strip(): operation
        for operation in document.operations or []
        if operation.get("path") and operation.get("method")
    }


def openapi_diff(db: Session, baseline_build: Build, current_build: Build) -> dict[str, Any]:
    baseline_operations = openapi_operations(db, baseline_build)
    current_operations = openapi_operations(db, current_build)
    if not baseline_operations or not current_operations:
        return {
            "available": False,
            "reason": "Both builds need an OpenAPI revision to compare operations.",
            "added": [],
            "changed": [],
            "removed": [],
        }
    baseline_keys = set(baseline_operations)
    current_keys = set(current_operations)
    changed = [
        key
        for key in sorted(baseline_keys & current_keys)
        if baseline_operations[key].get("operation_id")
        != current_operations[key].get("operation_id")
        or baseline_operations[key].get("summary") != current_operations[key].get("summary")
    ]
    return {
        "available": True,
        "reason": "",
        "added": sorted(current_keys - baseline_keys),
        "changed": changed,
        "removed": sorted(baseline_keys - current_keys),
    }


def _severity_rank(value: str) -> int:
    try:
        return SEVERITY_ORDER[Severity(value)]
    except ValueError:
        return 5


def build_release_plan(db: Session, run: Run) -> dict[str, Any]:
    """Snapshot the candidate set and eligible recipe revisions at submission time."""
    baseline = db.get(Run, run.baseline_run_id) if run.baseline_run_id else None
    candidates: list[dict[str, Any]] = []
    seen: set[uuid.UUID] = set()
    if baseline is not None:
        for item in build_run_view(db, baseline):
            finding = item.finding
            if finding.id in seen:
                continue
            seen.add(finding.id)
            candidates.append(_candidate(db, run, finding, baseline))
    # Findings with accepted evidence on the build but no baseline row still belong in
    # the plan: absence from an earlier report is not proof of absence.
    if baseline is not None:
        rows = db.execute(select(Finding).where(Finding.project_id == run.project_id)).scalars()
        for finding in rows:
            if finding.id in seen:
                continue
            state = state_for_build(db, finding.id, baseline.build_id)
            if state.observation_id is None:
                continue
            seen.add(finding.id)
            candidates.append(_candidate(db, run, finding, baseline))

    candidates.sort(
        key=lambda item: (
            # Open Critical/High first, then remaining Ready-for-Retest cases, then the rest.
            0
            if item["severity"] in {Severity.CRITICAL.value, Severity.HIGH.value}
            else (1 if item["marked_ready"] else 2),
            _severity_rank(item["severity"]),
            item.get("created_at") or "",
            item["public_id"],
        )
    )
    current_build = db.get(Build, run.build_id)
    baseline_build = db.get(Build, baseline.build_id) if baseline is not None else None
    diff = (
        openapi_diff(db, baseline_build, current_build)
        if baseline_build is not None and current_build is not None
        else {
            "available": False,
            "reason": "A comparison baseline is required to diff OpenAPI operations.",
            "added": [],
            "changed": [],
            "removed": [],
        }
    )
    discovery_candidates = [
        {
            "method": key.split(" ", 1)[0],
            "route": key.split(" ", 1)[1] if " " in key else key,
            "reason": "added operation",
        }
        for key in diff["added"]
    ] + [
        {
            "method": key.split(" ", 1)[0],
            "route": key.split(" ", 1)[1] if " " in key else key,
            "reason": "changed operation",
        }
        for key in diff["changed"]
    ]
    limits = run.budget or {}
    max_checks = int(limits.get("max_checks", 12))
    replay_allocation = min(int(limits.get("max_replay_checks", 12)), max_checks)
    replay_count = 0
    for candidate in candidates:
        if candidate["action"] != RetestMethod.AUTOMATIC.value:
            continue
        if replay_count >= replay_allocation:
            candidate["action"] = "skipped"
            candidate["reason"] = (
                "Replay allocation exhausted; remaining budget kept for discovery."
            )
            continue
        replay_count += 1
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "baseline_run_id": str(baseline.id) if baseline else None,
        "candidates": candidates,
        "selection_rules": [
            "Open Critical and High cases first",
            "Then findings an operator marked Ready for Retest",
            "Then remaining open cases by severity and age",
            "Guided and needs-validation cases stay visible as pending human action",
            "Replays are capped independently of the discovery allocation",
            "Added or changed OpenAPI operations are recorded as discovery candidates",
        ],
        "openapi_diff": diff,
        "discovery_candidates": discovery_candidates,
        "discovery_rationale": (
            "OpenAPI operations were unchanged; bounded recon may still surface changes."
            if diff["available"] and not diff["added"] and not diff["changed"]
            else (
                "Discovery focuses on added or changed OpenAPI operations."
                if discovery_candidates
                else "No OpenAPI operations were available to diff; recon is the only discovery source."
            )
        ),
        "budget": {
            "replay_checks": replay_count,
            "max_checks": max_checks,
            "discovery_allocation": max_checks - replay_count,
            "estimated_engine_cost_usd": limits.get("engine_budget_usd"),
            "spend_note": limits.get("estimated_cost_note"),
        },
        "previously_verified_included": any(
            c["previous_outcome"] == VerificationOutcome.FIX_VERIFIED.value for c in candidates
        ),
    }


def _candidate(db: Session, run: Run, finding: Finding, baseline: Run) -> dict[str, Any]:
    from app.models import ReadyMarker

    ready = (
        db.execute(
            select(ReadyMarker.id).where(
                ReadyMarker.finding_id == finding.id, ReadyMarker.build_id == run.build_id
            )
        ).scalar_one_or_none()
        is not None
    )
    state = state_for_build(db, finding.id, baseline.build_id)
    pair = approved_recipe(db, finding.id)
    method = eligibility(finding)
    action = method
    reason = ""
    if finding.disposition != "open":
        action = "skipped"
        reason = f"Finding is marked {finding.disposition}"
    elif method == RetestMethod.PENDING_EVIDENCE_REVIEW.value:
        action = "skipped"
        reason = "Evidence needs validation before replay can run"
    elif method == RetestMethod.GUIDED.value:
        action = "guided_pending"
        reason = "Guided retest needs a human besides the scan"
    elif pair is None:
        action = "skipped"
        reason = "No approved recipe revision is available"
    return {
        "finding_id": str(finding.id),
        "public_id": finding.public_id,
        "created_at": finding.created_at.isoformat(),
        "title": finding.title,
        "severity": finding.severity,
        "marked_ready": ready,
        "action": action,
        "reason": reason,
        "previous_outcome": state.outcome.value,
        "recipe_revision_id": str(pair[1].id) if pair else None,
        "recipe_revision": pair[1].revision if pair else None,
    }


def refresh_plan_actions(db: Session, run: Run) -> list[dict[str, Any]]:
    """Re-validate the snapshotted plan against current authorization before dispatch."""
    plan = (run.scope_snapshot or {}).get("release_plan") or {}
    candidates = list(plan.get("candidates") or [])
    for candidate in candidates:
        if candidate.get("action") != RetestMethod.AUTOMATIC.value:
            continue
        finding = db.get(Finding, uuid.UUID(candidate["finding_id"]))
        if finding is None or finding.disposition != "open":
            candidate["action"] = "skipped"
            candidate["reason"] = "Finding is no longer open"
            continue
        pair = approved_recipe(db, finding.id)
        if pair is None or str(pair[1].id) != str(candidate.get("recipe_revision_id")):
            candidate["action"] = "skipped"
            candidate["reason"] = "The approved recipe revision changed since submission"
    return candidates


def verify_known(
    db: Session,
    *,
    run: Run,
    settings: Settings,
    requester: User,
    progress=None,
) -> dict[str, Any]:
    candidates = refresh_plan_actions(db, run)
    attempted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    shared_failure: str | None = None
    for candidate in candidates:
        if progress is not None:
            progress()
        if candidate.get("action") != RetestMethod.AUTOMATIC.value:
            skipped.append(candidate)
            _record_pending_check(db, run, candidate)
            continue
        finding = db.get(Finding, uuid.UUID(candidate["finding_id"]))
        if finding is None:
            continue
        pair = approved_recipe(db, finding.id)
        if pair is None:
            candidate["action"] = "skipped"
            candidate["reason"] = "No approved recipe revision is available"
            skipped.append(candidate)
            continue
        project = db.get(Project, run.project_id)
        build = db.get(Build, run.build_id)
        if project is None or build is None:
            raise RuntimeError("run references a missing project or build")
        attempt = queue_automatic_attempt(
            db,
            project=project,
            finding=finding,
            build=build,
            actor=requester,
            mode=run.mode,
            settings=settings,
            run_id=run.id,
        )
        if attempt.state == "queued":
            execute_attempt(db, attempt=attempt, settings=settings)
        db.flush()
        outcome = attempt.outcome
        candidate["executed_revision"] = attempt.recipe_revision_label
        candidate["attempt_id"] = str(attempt.id)
        candidate["outcome"] = outcome
        attempted.append({**candidate, "attempt_id": str(attempt.id)})
        _record_replay_check(db, run, candidate, attempt)
        if attempt.reason_code in SHARED_FAILURE_REASONS:
            shared_failure = attempt.reason_code
            break
    return {
        "attempted": attempted,
        "skipped": skipped,
        "shared_failure": shared_failure,
        "attempted_count": len(attempted),
        "skipped_count": len(skipped),
    }


def _record_replay_check(db: Session, run: Run, candidate: dict[str, Any], attempt) -> None:
    check_key = f"verify:{candidate['public_id']}:{run.build_id}"[:160]
    existing = db.execute(
        select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.check_key == check_key)
    ).scalar_one_or_none()
    if existing is not None:
        return
    if attempt.outcome == VerificationOutcome.FIX_VERIFIED.value:
        result = CoverageResult.TESTED_NO_FINDING.value
    elif attempt.outcome == VerificationOutcome.STILL_REPRODUCIBLE.value:
        result = CoverageResult.FINDING_OBSERVED.value
    elif attempt.reason_code in {
        InconclusiveReason.SCOPE_DENIED.value,
        InconclusiveReason.POSITIVE_CONTROL_FAILED.value,
        InconclusiveReason.EXPIRED_CREDENTIALS.value,
        InconclusiveReason.MISSING_FIXTURE.value,
        InconclusiveReason.BUILD_IDENTITY_MISMATCH.value,
        InconclusiveReason.BUILD_IDENTITY_UNVERIFIED.value,
    }:
        result = CoverageResult.BLOCKED.value
    else:
        result = CoverageResult.NEEDS_REVIEW.value
    db.add(
        RunCheck(
            project_id=run.project_id,
            run_id=run.id,
            finding_id=uuid.UUID(candidate["finding_id"]),
            check_key=check_key,
            stage="verify_known",
            scenario_code="verify-known-finding",
            scenario_title=f"Verify {candidate['public_id']}: {candidate['title']}"[:200],
            surface=candidate.get("title", "")[:300],
            method="REPLAY",
            actor_label=attempt.recipe_revision_label,
            approach=("Constrained read-only replay with a legitimate-owner positive control."),
            coverage_source="buktirilis-replay",
            result=result,
            result_detail=(attempt.reason_text or attempt.outcome or "")[:400],
        )
    )
    db.flush()


def _record_pending_check(db: Session, run: Run, candidate: dict[str, Any]) -> None:
    check_key = f"pending:{candidate['public_id']}:{run.build_id}"[:160]
    existing = db.execute(
        select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.check_key == check_key)
    ).scalar_one_or_none()
    if existing is not None:
        return
    action = candidate.get("action")
    result = (
        CoverageResult.NOT_RUN.value
        if action in {"guided_pending", "skipped"}
        else CoverageResult.NEEDS_REVIEW.value
    )
    db.add(
        RunCheck(
            project_id=run.project_id,
            run_id=run.id,
            finding_id=uuid.UUID(candidate["finding_id"]),
            check_key=check_key,
            stage="verify_known",
            scenario_code="pending-human-action",
            scenario_title=f"Pending human action for {candidate['public_id']}"[:200],
            surface=candidate.get("title", "")[:300],
            method="MANUAL",
            approach="Guided retest or evidence review required",
            coverage_source="buktirilis-plan",
            result=result,
            result_detail=(candidate.get("reason") or "Pending human action")[:400],
        )
    )
    db.flush()


def discovery_decision(db: Session, run: Run, verify_result: dict[str, Any]) -> tuple[bool, str]:
    """Whether stage 2 may run, and a user-readable reason when it may not."""
    if verify_result.get("shared_failure"):
        return False, (
            "Discovery was skipped because a shared prerequisite failed "
            f"({verify_result['shared_failure']})."
        )
    plan = (run.scope_snapshot or {}).get("release_plan") or {}
    budget = plan.get("budget") or {}
    if int(budget.get("discovery_allocation", 0)) <= 0:
        return False, (
            "Discovery did not run: the replay allocation consumed the full check budget."
        )
    return True, ""


def coverage_gap_note(baseline_state: str, latest_state: str) -> str:
    return f"Previously {baseline_state}; latest verification is {latest_state}."


_ = (latest_observation, ObservationOutcome)
