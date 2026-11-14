"""Finding identity, verification state, and comparison semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain import VerificationOutcome
from app.services.findings import (
    build_run_view,
    bucket_counts,
    compare_scope,
    comparison_findings,
    compute_fingerprint,
    state_for_build,
)
from tests.helpers import add_observation, make_finding, make_run

T0 = datetime(2024, 10, 1, 12, 0, tzinfo=UTC)


def _run(db, lab_project, label, when, *, mode="demo"):
    run = make_run(db, lab_project.project, lab_project.builds[label], lab_project.operator)
    run.started_at = when
    run.completed_at = when + timedelta(minutes=5)
    run.snapshot_at = run.completed_at
    run.mode = mode
    run.scope_snapshot = {
        "base_url": lab_project.builds[label].target_url,
        "origins_signature": "http://127.0.0.1:18099::/deployments",
        "surfaces": ["/api/invoices/{invoice_id}"],
    }
    db.flush()
    return run


def test_fingerprint_is_stable_and_normalised():
    first = compute_fingerprint(
        issue_class="Broken Object Level Authorization",
        scope="GET /api/invoices/{invoice_id}/",
        actor_boundary="tenant-b  →  tenant-a",
        condition="Tenant Mismatch",
    )
    second = compute_fingerprint(
        issue_class="broken object level authorization",
        scope="get /api/invoices/{invoice_id}",
        actor_boundary="tenant-b → tenant-a",
        condition="tenant mismatch",
    )
    assert first == second
    different = compute_fingerprint(
        issue_class="broken object level authorization",
        scope="get /api/invoices/{invoice_id}",
        actor_boundary="tenant-c → tenant-a",
        condition="tenant mismatch",
    )
    assert first != different


def test_newest_observation_supersedes_earlier_fix_on_same_build(db, lab_project):
    finding = make_finding(db, lab_project.project)
    build = lab_project.builds["2024.10.1"]
    add_observation(db, finding, build, outcome="not_observed", observed_at=T0)
    assert state_for_build(db, finding.id, build.id).outcome == VerificationOutcome.FIX_VERIFIED
    add_observation(
        db, finding, build, outcome="observed", observed_at=T0 + timedelta(hours=1)
    )
    state = state_for_build(db, finding.id, build.id)
    assert state.outcome == VerificationOutcome.STILL_REPRODUCIBLE
    # Chronology is preserved, so historical snapshots stay stable.
    assert (
        state_for_build(db, finding.id, build.id, as_of=T0 + timedelta(minutes=30)).outcome
        == VerificationOutcome.FIX_VERIFIED
    )


def test_late_older_build_result_cannot_change_newer_build(db, lab_project):
    finding = make_finding(db, lab_project.project)
    newer = lab_project.builds["2024.10.2"]
    older = lab_project.builds["2024.10.1"]
    add_observation(db, finding, newer, outcome="not_observed", observed_at=T0)
    add_observation(
        db, finding, older, outcome="observed", observed_at=T0 + timedelta(days=3)
    )
    assert state_for_build(db, finding.id, newer.id).outcome == VerificationOutcome.FIX_VERIFIED


def test_absent_finding_is_not_inferred_fixed(db, lab_project):
    finding = make_finding(db, lab_project.project)
    run = _run(db, lab_project, "2024.10.2", T0)
    # No observation at all for this build: awaiting verification, not fixed.
    state = state_for_build(db, finding.id, run.build_id)
    assert state.outcome == VerificationOutcome.AWAITING_RETEST
    assert state.reason_text


def test_regression_and_still_reproducible_comparisons(db, lab_project):
    finding = make_finding(db, lab_project.project)
    run_a = _run(db, lab_project, "2024.10.1", T0)
    run_b = _run(db, lab_project, "2024.10.2", T0 + timedelta(days=7))
    run_c = _run(db, lab_project, "2024.10.3", T0 + timedelta(days=14))
    add_observation(db, finding, run_a.build_id, outcome="not_observed", observed_at=T0, run=run_a)
    add_observation(
        db, finding, run_b.build_id, outcome="observed", observed_at=T0 + timedelta(days=7), run=run_b
    )
    add_observation(
        db, finding, run_c.build_id, outcome="observed", observed_at=T0 + timedelta(days=14), run=run_c
    )
    b_rows = comparison_findings(db, run_a, run_b)
    c_rows = comparison_findings(db, run_b, run_c)
    assert b_rows[0]["bucket"] == "regressed"
    assert c_rows[0]["bucket"] == "still_reproducible"


def test_newly_observed_and_fix_verified_buckets(db, lab_project):
    old = make_finding(db, lab_project.project)
    new = make_finding(
        db,
        lab_project.project,
        title="Cross-tenant export",
        issue_class="cross-tenant-export",
        severity="critical",
        scope="GET /api/exports/{invoice_id}/pdf",
        actors="tenant-b -> tenant-a export",
    )
    run_a = _run(db, lab_project, "2024.10.1", T0)
    run_b = _run(db, lab_project, "2024.10.2", T0 + timedelta(days=7))
    add_observation(db, old, run_a.build_id, outcome="observed", observed_at=T0, run=run_a)
    add_observation(
        db, old, run_b.build_id, outcome="not_observed", observed_at=T0 + timedelta(days=7), run=run_b
    )
    add_observation(
        db, new, run_b.build_id, outcome="observed", observed_at=T0 + timedelta(days=7), run=run_b
    )
    rows = comparison_findings(db, run_a, run_b)
    buckets = {row["public_id"]: row["bucket"] for row in rows}
    assert buckets[old.public_id] == "fix_verified"
    assert buckets[new.public_id] == "newly_observed"
    counts = bucket_counts(rows)
    assert counts["fix_verified"] == 1
    assert counts["newly_observed"] == 1


def test_awaiting_and_needs_validation_are_separate(db, lab_project):
    weak = make_finding(
        db,
        lab_project.project,
        title="Rate limiting claim",
        issue_class="evidence-review",
        severity="medium",
        scope="GET /api/invoices",
        actors="anonymous",
        evidence_status="needs_validation",
    )
    pending = make_finding(
        db,
        lab_project.project,
        title="Approval flow",
        issue_class="two-actor-approval",
        scope="POST /api/approvals",
        actors="two actors",
    )
    run_a = _run(db, lab_project, "2024.10.1", T0)
    run_b = _run(db, lab_project, "2024.10.2", T0 + timedelta(days=7))
    add_observation(db, weak, run_a.build_id, outcome="observed", observed_at=T0, run=run_a)
    add_observation(db, pending, run_a.build_id, outcome="observed", observed_at=T0, run=run_a)
    rows = comparison_findings(db, run_a, run_b)
    buckets = {row["public_id"]: row["bucket"] for row in rows}
    assert buckets[weak.public_id] == "needs_validation"
    assert buckets[pending.public_id] == "awaiting_verification"
    detail = next(row for row in rows if row["public_id"] == pending.public_id)
    assert "absence" in detail["bucket_reason"].lower()


def test_historical_run_view_is_stable_after_later_retest(db, lab_project):
    finding = make_finding(db, lab_project.project)
    run_a = _run(db, lab_project, "2024.10.1", T0)
    add_observation(db, finding, run_a.build_id, outcome="observed", observed_at=T0, run=run_a)
    before = build_run_view(db, run_a)[0]
    assert before.state.outcome == VerificationOutcome.STILL_REPRODUCIBLE
    add_observation(
        db,
        finding,
        run_a.build_id,
        outcome="not_observed",
        observed_at=T0 + timedelta(days=2),
        source="replay",
    )
    after = build_run_view(db, run_a)[0]
    assert after.observations and after.observations[0].outcome == "observed"
    assert after.latest_verification is not None
    assert after.latest_verification.outcome == VerificationOutcome.FIX_VERIFIED


def test_stale_observation_is_not_a_verdict(db, lab_project):
    finding = make_finding(db, lab_project.project)
    build = lab_project.builds["2024.10.2"]
    add_observation(
        db, finding, build, outcome="not_observed", observed_at=T0, stale=True
    )
    state = state_for_build(db, finding.id, build.id)
    assert state.outcome == VerificationOutcome.AWAITING_RETEST
    assert state.stale is True


def test_mode_mismatch_makes_comparison_incomparable(db, lab_project):
    run_a = _run(db, lab_project, "2024.10.1", T0, mode="live")
    run_b = _run(db, lab_project, "2024.10.2", T0 + timedelta(days=1), mode="demo")
    scope = compare_scope(run_a, run_b)
    assert scope["comparable"] is False
    assert "demo" in scope["incomparable_reason"].lower()
