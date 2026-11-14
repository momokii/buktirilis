"""Finding identity, verification state, counting, and comparison.

Verification is derived from evidence scoped to (finding, build, attempt) rather than
stored as a mutable flag. That is what keeps a historical run's observed results stable
while later retests appear only in a labelled "latest verification" panel.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import (
    CONCLUSIVE_OUTCOMES,
    INCONCLUSIVE_REASON_LABELS,
    OBSERVATION_CONCLUSIVE,
    OBSERVATION_TO_VERIFICATION,
    SEVERITY_ORDER,
    ComparisonBucket,
    CoverageResult,
    EvidenceStatus,
    InconclusiveReason,
    ObservationOutcome,
    RetestMethod,
    Severity,
    VerificationOutcome,
)
from app.models import (
    Evidence,
    Finding,
    Observation,
    Project,
    Recipe,
    RecipeRevision,
    RetestAttempt,
    Run,
    RunCheck,
)

_WHITESPACE = re.compile(r"\s+")


def normalise_scope(value: str) -> str:
    text = _WHITESPACE.sub(" ", (value or "").strip()).lower()
    text = re.sub(r"/+$", "", text)
    return text


def compute_fingerprint(
    *, issue_class: str, scope: str, actor_boundary: str, condition: str
) -> str:
    """Conservative fingerprint: all four parts must match to merge findings."""
    parts = [
        normalise_scope(issue_class),
        normalise_scope(scope),
        normalise_scope(actor_boundary),
        normalise_scope(condition),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def next_public_id(db: Session, project_id: uuid.UUID) -> str:
    existing = db.execute(
        select(Finding.public_id).where(Finding.project_id == project_id)
    ).scalars()
    highest = 0
    for public_id in existing:
        match = re.fullmatch(r"BR-(\d+)", public_id or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"BR-{highest + 1}"


def upsert_finding(
    db: Session,
    *,
    project: Project,
    run: Run,
    payload: dict[str, Any],
) -> Finding:
    """Match by fingerprint, or create a stable project-level finding."""
    fingerprint = payload["fingerprint"]
    finding = db.execute(
        select(Finding).where(Finding.project_id == project.id, Finding.fingerprint == fingerprint)
    ).scalar_one_or_none()
    if finding is not None:
        # Keep the original identity, title and evidence; merely refresh descriptive
        # fields when the new observation is at least as strong.
        if payload.get("severity") and _severity_rank(payload["severity"]) < _severity_rank(
            finding.severity
        ):
            finding.severity = payload["severity"]
        if payload.get("impact") and not finding.impact:
            finding.impact = payload["impact"]
        if payload.get("remediation") and not finding.remediation:
            finding.remediation = payload["remediation"]
        return finding

    finding = Finding(
        project_id=project.id,
        public_id=next_public_id(db, project.id),
        title=payload["title"][:300],
        severity=payload.get("severity", Severity.MEDIUM),
        issue_class=payload.get("issue_class", "dynamic"),
        scope_summary=(payload.get("scope_summary") or "")[:400],
        actors_summary=(payload.get("actors_summary") or "")[:300],
        impact=payload.get("impact") or "",
        expected_behavior=payload.get("expected_behavior") or "",
        observed_behavior=payload.get("observed_behavior") or "",
        remediation=payload.get("remediation") or "",
        prerequisites=list(payload.get("prerequisites") or []),
        reproduction_steps=list(payload.get("reproduction_steps") or []),
        root_cause_hypothesis=payload.get("root_cause_hypothesis"),
        fingerprint=fingerprint,
        evidence_status=payload.get("evidence_status", EvidenceStatus.SUPPORTED),
        retest_method=payload.get("retest_method", RetestMethod.GUIDED),
        first_run_id=run.id,
    )
    db.add(finding)
    db.flush()
    return finding


def _severity_rank(value: str) -> int:
    try:
        return SEVERITY_ORDER[Severity(value)]
    except ValueError:
        return 5


@dataclass(frozen=True)
class FindingState:
    """Current verification of one finding on one build."""

    finding_id: uuid.UUID
    outcome: VerificationOutcome
    observation_id: uuid.UUID | None = None
    source: str | None = None
    observed_at: datetime | None = None
    stale: bool = False
    reason_code: str | None = None
    reason_text: str = ""
    stale_note: str = ""


def latest_observation(
    db: Session,
    finding_id: uuid.UUID,
    build_id: uuid.UUID,
    *,
    as_of: datetime | None = None,
    conclusive_only: bool = False,
) -> Observation | None:
    stmt = (
        select(Observation)
        .where(
            Observation.finding_id == finding_id,
            Observation.build_id == build_id,
            Observation.accepted.is_(True),
        )
        .order_by(Observation.observed_at.desc(), Observation.recorded_at.desc())
        .limit(1)
    )
    if as_of is not None:
        stmt = stmt.where(Observation.observed_at <= as_of)
    if conclusive_only:
        stmt = stmt.where(Observation.outcome.in_([o.value for o in OBSERVATION_CONCLUSIVE]))
    return db.execute(stmt).scalar_one_or_none()


def _attempt_reason(db: Session, finding_id: uuid.UUID, build_id: uuid.UUID) -> FindingState:
    attempt = db.execute(
        select(RetestAttempt)
        .where(
            RetestAttempt.finding_id == finding_id,
            RetestAttempt.build_id == build_id,
            RetestAttempt.state.in_(["queued", "running"]),
        )
        .order_by(RetestAttempt.requested_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if attempt is not None:
        return FindingState(
            finding_id=finding_id,
            outcome=VerificationOutcome.AWAITING_RETEST,
            reason_code="retest_queued",
            reason_text="Retest queued for this build",
        )
    last = db.execute(
        select(RetestAttempt)
        .where(
            RetestAttempt.finding_id == finding_id,
            RetestAttempt.build_id == build_id,
            RetestAttempt.outcome.is_not(None),
        )
        .order_by(RetestAttempt.requested_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last is not None and last.outcome == VerificationOutcome.INCONCLUSIVE.value:
        code = last.reason_code or InconclusiveReason.UNRECOGNIZED_RESPONSE.value
        return FindingState(
            finding_id=finding_id,
            outcome=VerificationOutcome.AWAITING_RETEST,
            reason_code=code,
            reason_text=last.reason_text
            or INCONCLUSIVE_REASON_LABELS.get(
                InconclusiveReason(code), "Latest retest was inconclusive"
            ),
        )
    if last is not None and last.state == "completed" and last.outcome is None:
        return FindingState(
            finding_id=finding_id,
            outcome=VerificationOutcome.AWAITING_RETEST,
            reason_code="manual_review_pending",
            reason_text="A guided submission is waiting for reviewer acceptance",
        )
    check = db.execute(
        select(RunCheck)
        .where(
            RunCheck.finding_id == finding_id,
            RunCheck.result.in_(
                [
                    CoverageResult.BLOCKED.value,
                    CoverageResult.NOT_RUN.value,
                    CoverageResult.NEEDS_REVIEW.value,
                ]
            ),
        )
        .order_by(RunCheck.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if check is not None:
        return FindingState(
            finding_id=finding_id,
            outcome=VerificationOutcome.AWAITING_RETEST,
            reason_code=f"check_{check.result}",
            reason_text=check.result_detail or f"Latest check was {check.result}",
        )
    return FindingState(
        finding_id=finding_id,
        outcome=VerificationOutcome.AWAITING_RETEST,
        reason_code="not_tested",
        reason_text="No comparable retest has completed on this build",
    )


def state_for_build(
    db: Session,
    finding_id: uuid.UUID,
    build_id: uuid.UUID,
    *,
    as_of: datetime | None = None,
) -> FindingState:
    observation = latest_observation(db, finding_id, build_id, as_of=as_of)
    if observation is None or observation.outcome not in {
        o.value for o in OBSERVATION_CONCLUSIVE
    }:
        if as_of is not None:
            return FindingState(
                finding_id=finding_id,
                outcome=VerificationOutcome.AWAITING_RETEST,
                reason_code="no_observation",
                reason_text="No accepted observation on this build as of this snapshot",
            )
        return _attempt_reason(db, finding_id, build_id)

    stale = bool((observation.detail or {}).get("stale"))
    outcome = OBSERVATION_TO_VERIFICATION[ObservationOutcome(observation.outcome)]
    if stale:
        return FindingState(
            finding_id=finding_id,
            outcome=VerificationOutcome.AWAITING_RETEST,
            observation_id=observation.id,
            source=observation.source,
            observed_at=observation.observed_at,
            stale=True,
            reason_code=InconclusiveReason.BUILD_IDENTITY_MISMATCH.value,
            reason_text="Verification is stale: recorded build or test conditions changed",
            stale_note=str((observation.detail or {}).get("stale_reason") or ""),
        )
    return FindingState(
        finding_id=finding_id,
        outcome=outcome,
        observation_id=observation.id,
        source=observation.source,
        observed_at=observation.observed_at,
    )


def newest_inconclusive(
    db: Session, finding_id: uuid.UUID, build_id: uuid.UUID
) -> RetestAttempt | None:
    return db.execute(
        select(RetestAttempt)
        .where(
            RetestAttempt.finding_id == finding_id,
            RetestAttempt.build_id == build_id,
            RetestAttempt.outcome == VerificationOutcome.INCONCLUSIVE.value,
        )
        .order_by(RetestAttempt.finished_at.desc().nullslast())
        .limit(1)
    ).scalar_one_or_none()


@dataclass
class RunFinding:
    finding: Finding
    state: FindingState
    run_checks: list[RunCheck] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    latest_attempt: RetestAttempt | None = None
    evidence_count: int = 0
    latest_verification: FindingState | None = None

    @property
    def row(self) -> dict[str, Any]:
        return finding_row(self)


def run_findings(db: Session, run: Run) -> list[Finding]:
    """Findings touched by this run, plus findings with accepted evidence on its build."""
    touched = set(
        db.execute(select(Observation.finding_id).where(Observation.run_id == run.id)).scalars()
    )
    touched.update(
        db.execute(
            select(RunCheck.finding_id).where(
                RunCheck.run_id == run.id, RunCheck.finding_id.is_not(None)
            )
        ).scalars()
    )
    touched.update(
        db.execute(
            select(Observation.finding_id).where(
                Observation.build_id == run.build_id, Observation.accepted.is_(True)
            )
        ).scalars()
    )
    if not touched:
        return []
    return list(
        db.execute(
            select(Finding)
            .where(Finding.project_id == run.project_id, Finding.id.in_(touched))
            .order_by(Finding.public_id)
        ).scalars()
    )


def build_run_view(db: Session, run: Run) -> list[RunFinding]:
    snapshot_at = run.completed_at
    results: list[RunFinding] = []
    for finding in run_findings(db, run):
        state = state_for_build(db, finding.id, run.build_id)
        checks = list(
            db.execute(
                select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.finding_id == finding.id)
            ).scalars()
        )
        observations = list(
            db.execute(
                select(Observation)
                .where(Observation.finding_id == finding.id, Observation.run_id == run.id)
                .order_by(Observation.observed_at)
            ).scalars()
        )
        attempt = db.execute(
            select(RetestAttempt)
            .where(RetestAttempt.run_id == run.id, RetestAttempt.finding_id == finding.id)
            .order_by(RetestAttempt.requested_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        evidence_count = db.execute(
            select(Evidence.id).where(Evidence.finding_id == finding.id)
        ).all()
        latest_verification = None
        if snapshot_at is not None:
            current = state_for_build(db, finding.id, run.build_id)
            if (
                current.observed_at is not None
                and current.observed_at > snapshot_at
                and current.outcome in CONCLUSIVE_OUTCOMES
            ):
                latest_verification = current
        results.append(
            RunFinding(
                finding=finding,
                state=state,
                run_checks=checks,
                observations=observations,
                latest_attempt=attempt,
                evidence_count=len(evidence_count),
                latest_verification=latest_verification,
            )
        )
    return results


def run_outcome(db: Session, run: Run, finding: Finding) -> str | None:
    """The outcome recorded *by this run* (not later retests)."""
    observation = db.execute(
        select(Observation)
        .where(
            Observation.finding_id == finding.id,
            Observation.run_id == run.id,
            Observation.outcome.in_([o.value for o in OBSERVATION_CONCLUSIVE]),
        )
        .order_by(Observation.observed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if observation is not None:
        return observation.outcome
    attempt = db.execute(
        select(RetestAttempt)
        .where(RetestAttempt.run_id == run.id, RetestAttempt.finding_id == finding.id)
        .order_by(RetestAttempt.requested_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if attempt is not None:
        return attempt.outcome
    check = (
        db.execute(
            select(RunCheck).where(RunCheck.run_id == run.id, RunCheck.finding_id == finding.id)
        )
        .scalars()
        .first()
    )
    if check is not None:
        return check.result
    return None


def finding_row(item: RunFinding, *, run: Run | None = None) -> dict[str, Any]:
    finding = item.finding
    return {
        "id": str(finding.id),
        "public_id": finding.public_id,
        "title": finding.title,
        "severity": finding.severity,
        "issue_class": finding.issue_class,
        "scope_summary": finding.scope_summary,
        "actors_summary": finding.actors_summary,
        "evidence_status": finding.evidence_status,
        "retest_method": eligibility(finding),
        "disposition": finding.disposition,
        "verification": {
            "outcome": item.state.outcome.value,
            "source": item.state.source,
            "observed_at": _iso(item.state.observed_at),
            "reason_code": item.state.reason_code,
            "reason": item.state.reason_text,
            "stale": item.state.stale,
        },
        "latest_verification": (
            {
                "outcome": item.latest_verification.outcome.value,
                "build_id": str(run.build_id) if run else None,
                "observed_at": _iso(item.latest_verification.observed_at),
            }
            if item.latest_verification
            else None
        ),
        "evidence_count": item.evidence_count,
        "last_attempt_at": _iso(item.latest_attempt.finished_at or item.latest_attempt.requested_at)
        if item.latest_attempt
        else None,
        "run_outcome": run_outcome_source(item),
    }


def run_outcome_source(item: RunFinding) -> str | None:
    for observation in sorted(item.observations, key=lambda o: o.observed_at, reverse=True):
        if observation.outcome in {o.value for o in OBSERVATION_CONCLUSIVE}:
            return observation.outcome
    if item.latest_attempt is not None:
        return item.latest_attempt.outcome
    for check in item.run_checks:
        if check.result in {
            CoverageResult.FINDING_OBSERVED.value,
            CoverageResult.TESTED_NO_FINDING.value,
            CoverageResult.BLOCKED.value,
            CoverageResult.NOT_RUN.value,
        }:
            return check.result
    return None


def eligibility(finding: Finding) -> str:
    """Choose the retest path independently of the evidence decision."""
    if finding.evidence_status == EvidenceStatus.NEEDS_VALIDATION:
        return RetestMethod.PENDING_EVIDENCE_REVIEW.value
    return finding.retest_method


def approved_recipe(db: Session, finding_id: uuid.UUID) -> tuple[Recipe, RecipeRevision] | None:
    recipe = db.execute(
        select(Recipe).where(Recipe.finding_id == finding_id, Recipe.state == "approved")
    ).scalar_one_or_none()
    if recipe is None:
        return None
    revision = db.execute(
        select(RecipeRevision)
        .where(RecipeRevision.recipe_id == recipe.id, RecipeRevision.approved_at.is_not(None))
        .order_by(RecipeRevision.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    if revision is None:
        return None
    return recipe, revision


def severity_counts(rows: list[RunFinding]) -> dict[str, int]:
    counts = {severity.value: 0 for severity in Severity}
    for item in rows:
        if item.finding.disposition != "open":
            continue
        counts[item.finding.severity] = counts.get(item.finding.severity, 0) + 1
    return counts


def coverage_counts(db: Session, run: Run) -> dict[str, Any]:
    rows = db.execute(select(RunCheck).where(RunCheck.run_id == run.id)).scalars().all()
    counts = {result.value: 0 for result in CoverageResult}
    for row in rows:
        counts[row.result] = counts.get(row.result, 0) + 1
    total = len(rows)
    unknown = counts[CoverageResult.PLANNED.value] + counts[CoverageResult.NOT_RUN.value]
    return {
        "total": total,
        "counts": counts,
        "unknown": unknown,
        "denominator": total,
        "surfaces_checked": len(
            {row.surface for row in rows if row.result == CoverageResult.TESTED_NO_FINDING.value
             or row.result == CoverageResult.FINDING_OBSERVED.value}
        ),
        "coverage_complete": run.coverage_complete,
    }


def comparison_findings(db: Session, baseline: Run | None, current: Run) -> list[dict[str, Any]]:
    """Assign each comparable finding exactly one primary bucket."""
    current_rows = build_run_view(db, current)
    baseline_snapshot: dict[uuid.UUID, FindingState] = {}
    if baseline is not None and baseline.completed_at is not None:
        for item in build_run_view(db, baseline):
            state = state_for_build(
                db, item.finding.id, baseline.build_id, as_of=baseline.completed_at
            )
            baseline_snapshot[item.finding.id] = state

    seen: set[uuid.UUID] = set()
    rows: list[dict[str, Any]] = []
    for item in current_rows:
        seen.add(item.finding.id)
        base_state = baseline_snapshot.get(item.finding.id)
        bucket, reason = _bucket(item, base_state)
        rows.append(
            {
                **finding_row(item, run=current),
                "bucket": bucket.value,
                "bucket_reason": reason,
                "baseline_outcome": base_state.outcome.value if base_state else None,
                "baseline_reason": base_state.reason_text if base_state else None,
                "in_current_run": bool(item.observations or item.run_checks),
            }
        )
    if baseline is not None:
        for finding_id, base_state in baseline_snapshot.items():
            if finding_id in seen:
                continue
            finding = db.get(Finding, finding_id)
            if finding is None:
                continue
            bucket, reason = _absent_bucket(finding, base_state)
            rows.append(
                {
                    "id": str(finding.id),
                    "public_id": finding.public_id,
                    "title": finding.title,
                    "severity": finding.severity,
                    "issue_class": finding.issue_class,
                    "scope_summary": finding.scope_summary,
                    "actors_summary": finding.actors_summary,
                    "evidence_status": finding.evidence_status,
                    "retest_method": eligibility(finding),
                    "disposition": finding.disposition,
                    "verification": {
                        "outcome": VerificationOutcome.AWAITING_RETEST.value,
                        "source": None,
                        "observed_at": None,
                        "reason_code": "not_tested_in_run",
                        "reason": "Not tested on this build",
                        "stale": False,
                    },
                    "latest_verification": None,
                    "evidence_count": 0,
                    "last_attempt_at": None,
                    "run_outcome": None,
                    "bucket": bucket.value,
                    "bucket_reason": reason,
                    "baseline_outcome": base_state.outcome.value,
                    "baseline_reason": base_state.reason_text,
                    "in_current_run": False,
                }
            )
    rows.sort(
        key=lambda row: (
            _severity_rank(row["severity"]),
            row["public_id"],
        )
    )
    return rows


def _absent_bucket(finding: Finding, base_state: FindingState) -> tuple[ComparisonBucket, str]:
    if finding.evidence_status == EvidenceStatus.NEEDS_VALIDATION:
        return (
            ComparisonBucket.NEEDS_VALIDATION,
            "Evidence needs validation before a verdict can be compared",
        )
    if finding.disposition != "open":
        return (ComparisonBucket.INCOMPARABLE, f"Finding is marked {finding.disposition}")
    return (
        ComparisonBucket.AWAITING_VERIFICATION,
        "No comparable evidence on this build; absence is not evidence of a fix",
    )


def _bucket(item: RunFinding, base_state: FindingState | None) -> tuple[ComparisonBucket, str]:
    finding = item.finding
    if finding.disposition != "open":
        return (ComparisonBucket.INCOMPARABLE, f"Finding is marked {finding.disposition}")
    if item.state.stale:
        return (ComparisonBucket.INCOMPARABLE, item.state.stale_note or "Verification is stale")
    outcome = item.state.outcome
    if outcome == VerificationOutcome.FIX_VERIFIED:
        return (ComparisonBucket.FIX_VERIFIED, "Prevented on this build with a valid control")
    if outcome == VerificationOutcome.STILL_REPRODUCIBLE:
        base_outcome = base_state.outcome if base_state else None
        if base_outcome == VerificationOutcome.FIX_VERIFIED:
            return (
                ComparisonBucket.REGRESSED,
                "Baseline snapshot recorded a verified fix under comparable conditions",
            )
        if base_outcome in {None, VerificationOutcome.AWAITING_RETEST}:
            return (
                ComparisonBucket.NEWLY_OBSERVED,
                "No accepted observation as of the selected baseline snapshot",
            )
        return (
            ComparisonBucket.STILL_REPRODUCIBLE,
            "Previously known and reproduced on this build",
        )
    if finding.evidence_status == EvidenceStatus.NEEDS_VALIDATION:
        return (
            ComparisonBucket.NEEDS_VALIDATION,
            "Evidence needs validation before a verdict can be compared",
        )
    return (
        ComparisonBucket.AWAITING_VERIFICATION,
        item.state.reason_text or "Awaiting verification",
    )


def bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {bucket.value: 0 for bucket in ComparisonBucket}
    for row in rows:
        counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1
    return counts


def latest_verification_panel(
    db: Session, run: Run, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Evidence recorded after this run's snapshot, labelled separately."""
    panel: list[dict[str, Any]] = []
    if run.completed_at is None:
        return panel
    for row in rows:
        finding_id = uuid.UUID(row["id"])
        latest = latest_observation(db, finding_id, run.build_id)
        if latest is None or latest.observed_at <= run.completed_at:
            continue
        if latest.outcome not in {o.value for o in OBSERVATION_CONCLUSIVE}:
            continue
        panel.append(
            {
                "finding_id": row["id"],
                "public_id": row["public_id"],
                "title": row["title"],
                "outcome": latest.outcome,
                "source": latest.source,
                "observed_at": _iso(latest.observed_at),
                "observation_id": str(latest.id),
            }
        )
    return panel


def duplicate_candidates(db: Session, finding: Finding) -> list[dict[str, Any]]:
    """Surface ambiguous same-surface findings for reviewer disposition."""
    candidates = db.execute(
        select(Finding).where(
            Finding.project_id == finding.project_id,
            Finding.id != finding.id,
            Finding.issue_class == finding.issue_class,
            Finding.scope_summary == finding.scope_summary,
            Finding.fingerprint != finding.fingerprint,
        )
    ).scalars()
    return [
        {"id": str(c.id), "public_id": c.public_id, "title": c.title, "disposition": c.disposition}
        for c in candidates
    ]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


__all__ = [
    "FindingState",
    "ObservationOutcome",
    "RunFinding",
    "approved_recipe",
    "bucket_counts",
    "build_run_view",
    "compare_scope",
    "comparison_findings",
    "compute_fingerprint",
    "coverage_counts",
    "duplicate_candidates",
    "eligibility",
    "finding_row",
    "latest_observation",
    "latest_verification_panel",
    "newest_inconclusive",
    "next_public_id",
    "normalise_scope",
    "run_findings",
    "run_outcome",
    "severity_counts",
    "state_for_build",
    "upsert_finding",
]


def compare_scope(baseline: Run, current: Run) -> dict[str, Any]:
    """Describe scope/profile/coverage changes and any comparison limitation."""
    base_scope = baseline.scope_snapshot or {}
    cur_scope = current.scope_snapshot or {}
    limitations: list[str] = []
    incomparable_reason = ""
    if baseline.mode != current.mode:
        incomparable_reason = (
            "Demo records are excluded from live comparisons; select runs within the same mode."
        )
        limitations.append(incomparable_reason)
    if baseline.kind != current.kind:
        limitations.append(
            "The selected runs have different kinds; bucket labels remain evidence-based."
        )
    profile_changed = (
        baseline.profile_code != current.profile_code
        or baseline.profile_version != current.profile_version
    )
    if profile_changed:
        limitations.append(
            "The profile version changed between runs; compare coverage before drawing conclusions."
        )
    origins_changed = base_scope.get("origins_signature") != cur_scope.get("origins_signature")
    if origins_changed:
        limitations.append("The approved target origin or path restrictions changed between runs.")
    missing_scope = not base_scope or not cur_scope
    if missing_scope:
        limitations.append("One run has no recorded scope snapshot; comparison is limited.")
    coverage = {
        "baseline_complete": baseline.coverage_complete,
        "current_complete": current.coverage_complete,
        "baseline_estimated_cost_usd": (baseline.budget or {}).get("estimated_cost_usd"),
        "current_estimated_cost_usd": (current.budget or {}).get("estimated_cost_usd"),
    }
    assets = {
        "added": sorted(set(cur_scope.get("surfaces", [])) - set(base_scope.get("surfaces", []))),
        "removed": sorted(set(base_scope.get("surfaces", [])) - set(cur_scope.get("surfaces", []))),
    }
    return {
        "comparable": not incomparable_reason,
        "incomparable_reason": incomparable_reason,
        "profile_changed": profile_changed,
        "origins_changed": origins_changed,
        "path_restrictions_changed": base_scope.get("path_prefixes")
        != cur_scope.get("path_prefixes"),
        "limitations": limitations,
        "coverage": coverage,
        "surfaces": assets,
        "baseline_scope": base_scope,
        "current_scope": cur_scope,
    }
