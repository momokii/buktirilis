"""Automatic replay persistence, guided submission, review, and verdict transitions."""

from __future__ import annotations

from app.domain import AttemptKind, VerificationOutcome
from app.services.findings import state_for_build
from app.services.retests import (
    execute_attempt,
    mark_ready,
    queue_automatic_attempt,
    review_attempt,
    set_disposition,
    submit_guided,
    validate_evidence,
)
from tests.helpers import BOLA_RECIPE, approve_recipe, make_finding


def _setup(db, lab_project):
    finding = make_finding(db, lab_project.project)
    approve_recipe(db, lab_project.project, finding, lab_project.operator, BOLA_RECIPE)
    return finding


def test_automatic_attempt_records_observation_and_evidence(db, lab_project, settings):
    finding = _setup(db, lab_project)
    attempt = queue_automatic_attempt(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.1"],
        actor=lab_project.developer,
        mode="demo",
        settings=settings,
    )
    assert attempt.state == "queued"
    executed = execute_attempt(db, attempt=attempt, settings=settings)
    db.commit()
    assert executed.outcome == VerificationOutcome.STILL_REPRODUCIBLE.value
    state = state_for_build(db, finding.id, lab_project.builds["2024.10.1"].id)
    assert state.outcome == VerificationOutcome.STILL_REPRODUCIBLE
    from app.models import Evidence, Observation

    assert db.query(Observation).filter_by(attempt_id=executed.id).count() == 1
    evidence = db.query(Evidence).filter_by(attempt_id=executed.id).all()
    assert evidence
    assert "lab.tenant" not in str([row.payload for row in evidence])


def test_fix_verified_after_retest_on_patched_build(db, lab_project, settings):
    finding = _setup(db, lab_project)
    attempt = queue_automatic_attempt(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.2"],
        actor=lab_project.developer,
        mode="demo",
        settings=settings,
    )
    execute_attempt(db, attempt=attempt, settings=settings)
    db.commit()
    assert (
        state_for_build(db, finding.id, lab_project.builds["2024.10.2"].id).outcome
        == VerificationOutcome.FIX_VERIFIED
    )


def test_duplicate_submission_returns_same_active_attempt(db, lab_project, settings):
    finding = _setup(db, lab_project)
    first = queue_automatic_attempt(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.1"],
        actor=lab_project.developer,
        mode="demo",
        settings=settings,
    )
    db.commit()
    second = queue_automatic_attempt(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.1"],
        actor=lab_project.operator,
        mode="demo",
        settings=settings,
    )
    assert first.id == second.id
    from app.models import Job

    assert db.query(Job).filter_by(idempotency_key=f"retest:{first.id}").count() == 1


def test_inconclusive_attempt_never_creates_observation(db, lab_project, settings):
    finding = make_finding(db, lab_project.project)
    payload = dict(BOLA_RECIPE)
    payload["identity_refs"] = {"actor": "tenant-b-expired", "owner": "tenant-a-owner"}
    approve_recipe(db, lab_project.project, finding, lab_project.operator, payload)
    attempt = queue_automatic_attempt(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.1"],
        actor=lab_project.developer,
        mode="demo",
        settings=settings,
    )
    execute_attempt(db, attempt=attempt, settings=settings)
    db.commit()
    from app.models import Observation

    assert db.query(Observation).filter_by(finding_id=finding.id).count() == 0
    state = state_for_build(db, finding.id, lab_project.builds["2024.10.1"].id)
    assert state.outcome == VerificationOutcome.AWAITING_RETEST
    assert state.reason_code == "expired_credentials"


def test_guided_submission_stays_pending_until_accepted(db, lab_project):
    finding = make_finding(db, lab_project.project)
    attempt = submit_guided(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.2"],
        actor=lab_project.developer,
        outcome="fix_verified",
        notes="The cross-tenant read now returns 403; the owner still receives the invoice.",
        evidence_artifact_id=None,
        evidence_link="https://evidence.internal/atlas/guide-1",
        steps_revision=1,
        mode="demo",
    )
    db.commit()
    assert attempt.kind == AttemptKind.GUIDED.value
    assert (
        state_for_build(db, finding.id, lab_project.builds["2024.10.2"].id).outcome
        == VerificationOutcome.AWAITING_RETEST
    )
    from app.services.retests import attempt_row

    row = attempt_row(db, attempt)
    assert row["pending_review"] is True
    result = review_attempt(
        db,
        attempt=attempt,
        reviewer=lab_project.operator,
        decision="accepted",
        reason="Control request confirmed.",
    )
    db.commit()
    assert result["accepted"] is True
    assert (
        state_for_build(db, finding.id, lab_project.builds["2024.10.2"].id).outcome
        == VerificationOutcome.FIX_VERIFIED
    )


def test_changes_requested_keeps_verdict_and_preserves_submission(db, lab_project):
    finding = make_finding(db, lab_project.project)
    first = submit_guided(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.2"],
        actor=lab_project.developer,
        outcome="fix_verified",
        notes="Denied; no control captured.",
        evidence_artifact_id=None,
        evidence_link="https://evidence.internal/first",
        steps_revision=1,
        mode="demo",
    )
    db.commit()
    result = review_attempt(
        db,
        attempt=first,
        reviewer=lab_project.operator,
        decision="changes_requested",
        reason="Attach the legitimate-owner control response.",
    )
    db.commit()
    assert result["accepted"] is False
    assert (
        state_for_build(db, finding.id, lab_project.builds["2024.10.2"].id).outcome
        == VerificationOutcome.AWAITING_RETEST
    )
    second = submit_guided(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.2"],
        actor=lab_project.developer,
        outcome="still_reproducible",
        notes="Owner control works and the cross-tenant read still returns the object.",
        evidence_artifact_id=None,
        evidence_link="https://evidence.internal/second",
        steps_revision=1,
        mode="demo",
    )
    db.commit()
    from app.models import RetestAttempt

    assert db.query(RetestAttempt).filter_by(finding_id=finding.id).count() == 2
    assert first.id != second.id


def test_guided_submission_requires_evidence_for_conclusive_outcome(db, lab_project):
    finding = make_finding(db, lab_project.project)
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        submit_guided(
            db,
            project=lab_project.project,
            finding=finding,
            build=lab_project.builds["2024.10.2"],
            actor=lab_project.developer,
            outcome="fix_verified",
            notes="It looks fixed.",
            evidence_artifact_id=None,
            evidence_link="",
            steps_revision=1,
            mode="demo",
        )


def test_evidence_validation_changes_retest_method(db, lab_project):
    finding = make_finding(db, lab_project.project, evidence_status="needs_validation")
    assert finding.evidence_status == "needs_validation"
    validate_evidence(
        db,
        finding=finding,
        actor=lab_project.operator,
        status="supported",
        note="Reviewer confirmed the capture.",
    )
    db.commit()
    assert finding.evidence_status == "supported"
    assert finding.retest_method in {"automatic", "guided"}


def test_ready_marker_is_idempotent_and_does_not_change_verdict(db, lab_project):
    finding = make_finding(db, lab_project.project)
    first = mark_ready(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.2"],
        actor=lab_project.operator,
    )
    second = mark_ready(
        db,
        project=lab_project.project,
        finding=finding,
        build=lab_project.builds["2024.10.2"],
        actor=lab_project.operator,
    )
    db.commit()
    assert first.id == second.id
    assert (
        state_for_build(db, finding.id, lab_project.builds["2024.10.2"].id).outcome
        == VerificationOutcome.AWAITING_RETEST
    )


def test_disposition_requires_reason(db, lab_project):
    finding = make_finding(db, lab_project.project)
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        set_disposition(db, finding=finding, disposition="false_positive", reason="")
    set_disposition(
        db, finding=finding, disposition="false_positive", reason="Object is public by design."
    )
    db.commit()
    assert finding.disposition == "false_positive"
