"""Retest attempts, guided submissions, reviews, and verdict transitions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import (
    AttemptKind,
    AttemptState,
    EvidenceAttribution,
    EvidenceSource,
    EvidenceStatus,
    ObservationOutcome,
    RecipeState,
    RetestMethod,
    ReviewDecision,
    VerificationOutcome,
)
from app.models import (
    Artifact,
    Build,
    Evidence,
    Finding,
    Job,
    ManualReview,
    Observation,
    Project,
    ReadyMarker,
    RecipeRevision,
    RetestAttempt,
    TargetConfig,
    TestAccount,
    User,
)
from app.services.evidence import create_evidence
from app.services.findings import approved_recipe
from app.services.policy import TargetPolicy
from app.services.replays import evaluate_recipe, resolve_recipe_accounts


def utcnow() -> datetime:
    return datetime.now(UTC)


def mark_ready(
    db: Session, *, project: Project, finding: Finding, build: Build, actor: User
) -> ReadyMarker:
    existing = db.execute(
        select(ReadyMarker).where(
            ReadyMarker.finding_id == finding.id, ReadyMarker.build_id == build.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    marker = ReadyMarker(
        project_id=project.id,
        finding_id=finding.id,
        build_id=build.id,
        marked_by=actor.id,
        marked_at=utcnow(),
    )
    db.add(marker)
    db.flush()
    return marker


def is_ready(db: Session, finding_id: uuid.UUID, build_id: uuid.UUID) -> bool:
    return (
        db.execute(
            select(ReadyMarker.id).where(
                ReadyMarker.finding_id == finding_id, ReadyMarker.build_id == build_id
            )
        ).scalar_one_or_none()
        is not None
    )


def queue_automatic_attempt(
    db: Session,
    *,
    project: Project,
    finding: Finding,
    build: Build,
    actor: User,
    mode: str,
    settings: Settings,
    run_id: uuid.UUID | None = None,
) -> RetestAttempt:
    if build.project_id != project.id:
        raise HTTPException(status_code=400, detail="Build does not belong to this project")
    if finding.disposition != "open":
        raise HTTPException(
            status_code=409, detail="Only open findings can be retested automatically"
        )
    config = db.get(TargetConfig, build.target_config_id)
    if config is None:
        raise HTTPException(status_code=409, detail="Build has no recorded target configuration")
    policy = TargetPolicy.from_config(
        config, allow_loopback=bool(settings.allow_loopback_lab_targets)
    )
    try:
        policy.check(build.target_url)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail="The build target is outside the current approved scope",
        ) from exc

    pair = approved_recipe(db, finding.id)
    if pair is None:
        raise HTTPException(
            status_code=409,
            detail="No approved read-only replay recipe exists; use Guided Retest instead",
        )
    recipe, revision = pair
    if recipe.state != RecipeState.APPROVED:
        raise HTTPException(status_code=409, detail="The replay recipe is not approved")

    active = db.execute(
        select(RetestAttempt).where(
            RetestAttempt.finding_id == finding.id,
            RetestAttempt.build_id == build.id,
            RetestAttempt.state.in_([AttemptState.QUEUED, AttemptState.RUNNING]),
        )
    ).scalar_one_or_none()
    if active is not None:
        return active

    attempt = RetestAttempt(
        project_id=project.id,
        finding_id=finding.id,
        build_id=build.id,
        run_id=run_id,
        recipe_revision_id=revision.id,
        recipe_revision_label=f"r{revision.revision}",
        kind=AttemptKind.AUTOMATIC,
        state=AttemptState.QUEUED,
        requested_by=actor.id,
        requested_by_label=actor.display_name or actor.email,
        requested_at=utcnow(),
        build_identity_expected=build.expected_identity,
        mode=mode,
    )
    db.add(attempt)
    db.flush()
    job = Job(
        project_id=project.id,
        run_id=run_id,
        kind="retest",
        payload={"attempt_id": str(attempt.id)},
        state="queued",
        requested_by=actor.id,
        idempotency_key=f"retest:{attempt.id}",
    )
    db.add(job)
    db.flush()
    return attempt


def execute_attempt(db: Session, *, attempt: RetestAttempt, settings: Settings) -> RetestAttempt:
    if attempt.kind != AttemptKind.AUTOMATIC:
        raise HTTPException(
            status_code=409, detail="Only automatic attempts are executed by the runner"
        )
    if attempt.state == AttemptState.COMPLETED:
        return attempt
    attempt.state = AttemptState.RUNNING
    attempt.started_at = utcnow()
    db.flush()

    project = db.get(Project, attempt.project_id)
    finding = db.get(Finding, attempt.finding_id)
    build = db.get(Build, attempt.build_id)
    revision = (
        db.get(RecipeRevision, attempt.recipe_revision_id) if attempt.recipe_revision_id else None
    )
    if project is None or finding is None or build is None or revision is None:
        attempt.state = AttemptState.COMPLETED
        attempt.outcome = VerificationOutcome.INCONCLUSIVE.value
        attempt.reason_code = "missing_configuration"
        attempt.reason_text = "The attempt references records that no longer exist"
        attempt.finished_at = utcnow()
        db.flush()
        return attempt
    assert (
        project is not None and finding is not None and build is not None and revision is not None
    )

    config = db.get(TargetConfig, build.target_config_id)
    if config is None:
        attempt.state = AttemptState.COMPLETED
        attempt.outcome = VerificationOutcome.INCONCLUSIVE.value
        attempt.reason_code = "missing_configuration"
        attempt.reason_text = "The build target configuration is unavailable"
        attempt.finished_at = utcnow()
        db.flush()
        return attempt
    policy = TargetPolicy.from_config(
        config, allow_loopback=bool(settings.allow_loopback_lab_targets)
    )
    actor_account, owner_account = resolve_recipe_accounts(db, revision)
    if actor_account is None or owner_account is None:
        attempt.state = AttemptState.COMPLETED
        attempt.outcome = VerificationOutcome.INCONCLUSIVE.value
        attempt.reason_code = "missing_identity"
        attempt.reason_text = "The recipe references test identities that are no longer configured"
        attempt.finished_at = utcnow()
        db.flush()
        return attempt
    assert actor_account is not None and owner_account is not None

    result = evaluate_recipe(
        db,
        settings=settings,
        project=project,
        build=build,
        policy=policy,
        revision=revision,
        actor=actor_account,
        owner=owner_account,
    )

    attempt.state = AttemptState.COMPLETED
    attempt.outcome = result.outcome.value
    attempt.reason_code = result.reason_code
    attempt.reason_text = result.reason_text
    attempt.finished_at = utcnow()
    attempt.prerequisites = result.prerequisites
    attempt.positive_control = result.positive_control
    attempt.assertion_result = result.assertion_result
    attempt.build_identity_observed = result.build_identity_observed
    if result.build_identity_observed and (
        result.build_identity_observed == build.expected_identity
    ):
        build.identity_observed = True
    db.flush()

    for payload in result.evidence:
        create_evidence(
            db,
            project=project,
            finding_id=finding.id,
            run_id=attempt.run_id,
            attempt_id=attempt.id,
            build_id=build.id,
            kind="http_exchange",
            attribution=EvidenceAttribution.OBSERVED_CAPTURE,
            summary=str(payload.get("notes") or "Constrained replay capture")[:400],
            payload=payload,
            highlight=[str(h) for h in payload.get("highlight", [])],
            actor_label=str(payload.get("actor", "")),
            method=str((payload.get("request") or {}).get("method", "")),
            endpoint=str((payload.get("request") or {}).get("url", ""))[:400],
        )

    if result.is_conclusive:
        db.add(
            Observation(
                project_id=project.id,
                finding_id=finding.id,
                build_id=build.id,
                run_id=attempt.run_id,
                attempt_id=attempt.id,
                source=EvidenceSource.REPLAY.value,
                outcome=(
                    ObservationOutcome.OBSERVED.value
                    if result.outcome == VerificationOutcome.STILL_REPRODUCIBLE
                    else ObservationOutcome.NOT_OBSERVED.value
                ),
                accepted=True,
                recipe_revision_id=revision.id,
                observed_at=attempt.finished_at or utcnow(),
                detail={
                    "attempt_outcome": result.outcome.value,
                    "recipe_revision": revision.revision,
                    "build_identity": result.build_identity_observed,
                },
            )
        )
    db.flush()
    return attempt


def submit_guided(
    db: Session,
    *,
    project: Project,
    finding: Finding,
    build: Build,
    actor: User,
    outcome: str,
    notes: str,
    evidence_artifact_id: uuid.UUID | None,
    evidence_link: str,
    steps_revision: int,
    mode: str,
) -> RetestAttempt:
    if outcome not in {o.value for o in VerificationOutcome}:
        raise HTTPException(status_code=422, detail="Unknown verification outcome")
    if not notes.strip():
        raise HTTPException(
            status_code=422, detail="Notes describing what you observed are required"
        )
    if (
        outcome != VerificationOutcome.INCONCLUSIVE.value
        and evidence_artifact_id is None
        and not evidence_link.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="A conclusive guided result needs an attachment or an approved artifact link",
        )
    if evidence_artifact_id is not None:
        artifact = db.get(Artifact, evidence_artifact_id)
        if artifact is None or artifact.project_id != project.id:
            raise HTTPException(status_code=404, detail="Attachment not found in this project")
    attempt = RetestAttempt(
        project_id=project.id,
        finding_id=finding.id,
        build_id=build.id,
        kind=AttemptKind.GUIDED,
        state=AttemptState.COMPLETED,
        outcome=outcome if outcome in {o.value for o in VerificationOutcome} else None,
        reason_code=None,
        reason_text="",
        notes=notes.strip(),
        requested_by=actor.id,
        requested_by_label=actor.display_name or actor.email,
        requested_at=utcnow(),
        started_at=utcnow(),
        finished_at=utcnow(),
        prerequisites={
            "steps_revision": steps_revision,
            "outcome": outcome,
            "evidence_link": evidence_link.strip(),
            "evidence_artifact_id": str(evidence_artifact_id) if evidence_artifact_id else None,
        },
        mode=mode,
    )
    db.add(attempt)
    db.flush()
    create_evidence(
        db,
        project=project,
        finding_id=finding.id,
        run_id=None,
        attempt_id=attempt.id,
        build_id=build.id,
        kind="guided_submission",
        attribution=EvidenceAttribution.REVIEWER_SUBMISSION,
        summary=f"Guided retest submission: {outcome.replace('_', ' ')}",
        payload={
            "notes": notes.strip(),
            "evidence_link": evidence_link.strip(),
            "steps_revision": steps_revision,
            "outcome": outcome,
            "submitted_by": actor.display_name or actor.email,
            "submitted_at": attempt.requested_at.isoformat(),
        },
        artifact_id=evidence_artifact_id,
        actor_label=actor.display_name or actor.email,
        created_by=actor.id,
    )
    db.flush()
    return attempt


def review_attempt(
    db: Session,
    *,
    attempt: RetestAttempt,
    reviewer: User,
    decision: str,
    reason: str,
) -> dict[str, Any]:
    if attempt.kind != AttemptKind.GUIDED:
        raise HTTPException(status_code=409, detail="Only guided submissions need manual review")
    if decision not in {d.value for d in ReviewDecision}:
        raise HTTPException(status_code=422, detail="Unknown review decision")
    if decision == ReviewDecision.CHANGES_REQUESTED.value and not reason.strip():
        raise HTTPException(status_code=422, detail="A reason is required when requesting changes")
    if attempt.outcome is None:
        raise HTTPException(status_code=409, detail="This submission has no proposed outcome")
    review = ManualReview(
        project_id=attempt.project_id,
        attempt_id=attempt.id,
        reviewer_id=reviewer.id,
        reviewer_label=reviewer.display_name or reviewer.email,
        decision=decision,
        reason=reason.strip(),
        created_at=utcnow(),
    )
    db.add(review)
    db.flush()
    accepted_conclusive = (
        decision == ReviewDecision.ACCEPTED.value
        and attempt.outcome in {o.value for o in VerificationOutcome}
        and attempt.outcome
        in {
            VerificationOutcome.FIX_VERIFIED.value,
            VerificationOutcome.STILL_REPRODUCIBLE.value,
        }
    )
    if accepted_conclusive:
        existing = db.execute(
            select(Observation).where(Observation.attempt_id == attempt.id)
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                Observation(
                    project_id=attempt.project_id,
                    finding_id=attempt.finding_id,
                    build_id=attempt.build_id,
                    attempt_id=attempt.id,
                    source=EvidenceSource.GUIDED.value,
                    outcome=(
                        ObservationOutcome.OBSERVED.value
                        if attempt.outcome == VerificationOutcome.STILL_REPRODUCIBLE.value
                        else ObservationOutcome.NOT_OBSERVED.value
                    ),
                    accepted=True,
                    observed_at=attempt.finished_at or utcnow(),
                    detail={
                        "attempt_outcome": attempt.outcome,
                        "reviewed_by": reviewer.display_name or reviewer.email,
                        "review_id": str(review.id),
                    },
                )
            )
    db.flush()
    return {
        "review_id": str(review.id),
        "decision": decision,
        "accepted": accepted_conclusive,
        "attempt_id": str(attempt.id),
    }


def validate_evidence(
    db: Session,
    *,
    finding: Finding,
    actor: User,
    status: str,
    note: str,
) -> Finding:
    if status not in {s.value for s in EvidenceStatus}:
        raise HTTPException(status_code=422, detail="Unknown evidence status")
    finding.evidence_status = status
    if status == EvidenceStatus.NEEDS_VALIDATION.value:
        finding.retest_method = RetestMethod.PENDING_EVIDENCE_REVIEW.value
    else:
        pair = approved_recipe(db, finding.id)
        finding.retest_method = RetestMethod.AUTOMATIC.value if pair else RetestMethod.GUIDED.value
    if note:
        finding.disposition_reason = note.strip()
    db.flush()
    return finding


def set_disposition(db: Session, *, finding: Finding, disposition: str, reason: str) -> Finding:
    if disposition not in {"open", "false_positive", "duplicate"}:
        raise HTTPException(status_code=422, detail="Unknown disposition")
    if disposition != "open" and not reason.strip():
        raise HTTPException(status_code=422, detail="A reason is required to close a finding")
    finding.disposition = disposition
    finding.disposition_reason = reason.strip()
    db.flush()
    return finding


def identity_attestation(
    db: Session, *, build: Build, actor: User, observed_identity: str, note: str
) -> Build:
    identity = observed_identity.strip()
    if not identity:
        raise HTTPException(status_code=422, detail="A deployed build identity is required")
    if build.expected_identity and build.expected_identity != identity:
        raise HTTPException(
            status_code=409,
            detail="A different expected identity is already recorded for this build",
        )
    build.expected_identity = identity[:160]
    build.identity_attested_by = actor.id
    build.build_metadata = {
        **(build.build_metadata or {}),
        "identity_attestation_note": note.strip()[:400],
    }
    db.flush()
    return build


def attempt_row(
    db: Session, attempt: RetestAttempt, *, include_evidence: bool = True
) -> dict[str, Any]:
    build = db.get(Build, attempt.build_id)
    finding = db.get(Finding, attempt.finding_id)
    reviews = list(
        db.execute(
            select(ManualReview)
            .where(ManualReview.attempt_id == attempt.id)
            .order_by(ManualReview.created_at)
        ).scalars()
    )
    evidence_rows = (
        list(
            db.execute(
                select(Evidence)
                .where(Evidence.attempt_id == attempt.id)
                .order_by(Evidence.created_at)
            ).scalars()
        )
        if include_evidence
        else []
    )
    return {
        "id": str(attempt.id),
        "kind": attempt.kind,
        "state": attempt.state,
        "outcome": attempt.outcome,
        "reason_code": attempt.reason_code,
        "reason": attempt.reason_text,
        "notes": attempt.notes,
        "mode": attempt.mode,
        "build_id": str(attempt.build_id),
        "build_label": build.label if build else "",
        "finding_id": str(attempt.finding_id),
        "finding_public_id": finding.public_id if finding else "",
        "recipe_revision": attempt.recipe_revision_label,
        "requested_by": attempt.requested_by_label,
        "requested_at": _iso(attempt.requested_at),
        "started_at": _iso(attempt.started_at),
        "finished_at": _iso(attempt.finished_at),
        "build_identity": {
            "expected": attempt.build_identity_expected,
            "observed": attempt.build_identity_observed,
        },
        "prerequisites": attempt.prerequisites,
        "positive_control": attempt.positive_control,
        "assertion_result": attempt.assertion_result,
        "reviews": [
            {
                "id": str(review.id),
                "decision": review.decision,
                "reason": review.reason,
                "reviewer": review.reviewer_label,
                "created_at": _iso(review.created_at),
            }
            for review in reviews
        ],
        "pending_review": attempt.kind == AttemptKind.GUIDED
        and attempt.outcome is not None
        and not any(r.decision == ReviewDecision.ACCEPTED.value for r in reviews),
        "evidence": [evidence_row(row) for row in evidence_rows],
    }


def evidence_row(evidence: Evidence) -> dict[str, Any]:
    return {
        "id": str(evidence.id),
        "kind": evidence.kind,
        "attribution": evidence.attribution,
        "summary": evidence.summary,
        "actor_label": evidence.actor_label,
        "method": evidence.method,
        "endpoint": evidence.endpoint,
        "artifact_id": str(evidence.artifact_id) if evidence.artifact_id else None,
        "created_at": _iso(evidence.created_at),
        "payload": evidence.payload,
        "highlight": evidence.highlight,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def resolve_accounts_for_project(db: Session, project_id: uuid.UUID) -> list[TestAccount]:
    return list(
        db.execute(
            select(TestAccount)
            .where(TestAccount.project_id == project_id)
            .order_by(TestAccount.name)
        ).scalars()
    )
