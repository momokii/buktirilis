"""End-to-end pipeline tests: baseline, release scan, regression, cancel, revocation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain import RunKind
from app.models import Build, Job, Observation, ProjectMember, Run, RunCheck
from app.services import demo
from app.services.findings import (
    bucket_counts,
    comparison_findings,
    coverage_counts,
    state_for_build,
)
from app.services.ingest import ArtifactBundle, ingest_run
from app.services.pipeline import execute_run
from app.services.queue import reconcile
from app.services.runs import cancel_run, create_run
from tests.helpers import approve_recipe, make_finding, make_run


def _start(db, run):
    job = db.get(Job, run.job_id)
    job.state = "running"
    job.claimed_by = "test-worker"
    job.attempts = 1
    job.started_at = datetime.now(UTC)
    db.flush()
    return job


def _execute(db, run, settings):
    job = _start(db, run)
    execute_run(db, run=run, job=job, settings=settings)
    db.commit()
    return run


def _create(db, lab_project, settings, *, kind, build_label, baseline=None, actor=None):
    accounts = [
        account
        for account in db.query(__import__("app.models", fromlist=["TestAccount"]).TestAccount)
        if account.project_id == lab_project.project.id
        and account.name in {"tenant-a-owner", "tenant-b-dev"}
    ]
    run, _created = create_run(
        db,
        settings=settings,
        project=lab_project.project,
        build=lab_project.builds[build_label],
        kind=kind,
        depth="quick" if kind == RunKind.BASELINE else "standard",
        profile_code="web-api-access-control",
        profile_version=1,
        account_ids=[account.id for account in accounts],
        unauthenticated=False,
        baseline_run_id=baseline.id if baseline else None,
        actor=actor or lab_project.operator,
        accept_reduced_scope=True,
    )
    db.commit()
    return run


def test_demo_baseline_ingest_creates_findings_and_honest_coverage(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    run = _execute(db, run, settings)
    db.refresh(run)
    assert run.status == "completed", (run.failure_reason, run.limitations)
    assert run.mode == "demo"
    assert run.ingest_state == "complete"
    assert run.coverage_complete is False
    assert "Demo mode" in " ".join(run.limitations)
    from app.models import Finding

    findings = db.query(Finding).filter_by(project_id=lab_project.project.id).all()
    assert len(findings) == 3
    weak = next(f for f in findings if f.evidence_status == "needs_validation")
    assert weak.retest_method == "pending_evidence_review"
    coverage = coverage_counts(db, run)
    assert coverage["counts"]["finding_observed"] >= 2
    assert coverage["counts"]["not_run"] >= 1
    assert coverage["denominator"] >= coverage["counts"]["finding_observed"]
    assert "Coverage is incomplete" in run.summary


def test_ingest_is_idempotent_and_missing_artifacts_are_explicit(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    run = _execute(db, run, settings)
    db.refresh(run)
    before = (
        db.query(Observation).filter_by(run_id=run.id).count(),
        db.query(RunCheck).filter_by(run_id=run.id).count(),
    )
    job = db.get(Job, run.job_id)
    job.state = "running"
    db.flush()
    execute_run(db, run=run, job=job, settings=settings)
    db.commit()
    after = (
        db.query(Observation).filter_by(run_id=run.id).count(),
        db.query(RunCheck).filter_by(run_id=run.id).count(),
    )
    assert before == after

    empty_run = make_run(
        db, lab_project.project, lab_project.builds["2024.10.3"], lab_project.operator
    )
    result = ingest_run(
        db,
        run=empty_run,
        project=lab_project.project,
        build=lab_project.builds["2024.10.3"],
        bundle=ArtifactBundle(missing=["run.json", "vulnerabilities.json", "coverage.json"]),
    )
    db.commit()
    assert empty_run.ingest_state == "missing"
    assert empty_run.coverage_complete is False
    assert result["imported"] == 0
    assert any("No engine artifacts" in limitation for limitation in empty_run.limitations)


def test_narrowed_policy_stops_discovery_after_known_replay(db, lab_project, settings, monkeypatch):
    from app.models import TargetConfig
    from app.services import releases as releases_service

    baseline = _execute(
        db,
        _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1"),
        settings,
    )
    finding = next(
        row
        for row in db.query(__import__("app.models", fromlist=["Finding"]).Finding)
        if row.issue_class == "broken-object-authorization"
    )
    approve_recipe(db, lab_project.project, finding, lab_project.operator)
    db.commit()
    release = _create(
        db,
        lab_project,
        settings,
        kind=RunKind.RELEASE_SCAN,
        build_label="2024.10.2",
        baseline=baseline,
    )
    original = releases_service.verify_known

    def narrow_during_replay(*args, **kwargs):
        result = original(*args, **kwargs)
        db.add(
            TargetConfig(
                project_id=lab_project.project.id,
                revision=2,
                base_url=lab_project.lab_base,
                allowed_origins=[lab_project.lab_base],
                path_prefixes=["/different"],
                environment_label="staging",
                run_limits={},
                created_by=lab_project.admin.id,
            )
        )
        db.flush()
        return result

    monkeypatch.setattr(releases_service, "verify_known", narrow_during_replay)
    run = _execute(db, release, settings)
    db.refresh(run)
    assert run.status == "failed"
    assert "Discovery stopped" in (run.failure_reason or "")
    from app.models import RunStage

    stage = db.query(RunStage).filter_by(run_id=run.id, code="discovery").one()
    assert stage.state == "failed"


def test_cancel_queued_run_is_terminal_without_a_worker(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    cancel_run(db, run=run, actor=lab_project.operator, reason="No longer needed")
    db.commit()
    db.refresh(run)
    job = db.get(Job, run.job_id)
    db.refresh(job)
    assert run.status == "canceled"
    assert run.completed_at is not None
    assert job.state == "canceled"
    assert db.query(Job).filter_by(state="queued").count() == 0
    from app.models import RunStage

    stages = {row.code: row.state for row in db.query(RunStage).filter_by(run_id=run.id)}
    assert stages["preflight"] == "canceled"
    assert stages["discovery"] == "canceled"


def test_release_scan_verifies_fix_then_regresses(db, lab_project, settings):
    baseline = _execute(
        db,
        _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1"),
        settings,
    )
    bola = next(
        finding
        for finding in db.query(__import__("app.models", fromlist=["Finding"]).Finding).all()
        if finding.issue_class == "broken-object-authorization"
    )
    approve_recipe(db, lab_project.project, bola, lab_project.operator)
    db.commit()

    release_b = _execute(
        db,
        _create(
            db,
            lab_project,
            settings,
            kind=RunKind.RELEASE_SCAN,
            build_label="2024.10.2",
            baseline=baseline,
        ),
        settings,
    )
    db.refresh(release_b)
    assert release_b.status == "completed"
    assert state_for_build(db, bola.id, release_b.build_id).outcome.value == "fix_verified"
    export_finding = next(
        finding
        for finding in db.query(__import__("app.models", fromlist=["Finding"]).Finding).all()
        if finding.issue_class == "cross-tenant-export"
    )
    approve_recipe(
        db,
        lab_project.project,
        export_finding,
        lab_project.operator,
        {
            "method": "GET",
            "path_template": "/api/exports/{invoice_id}/pdf",
            "fixture_refs": [
                {
                    "name": "invoice_id",
                    "value": "INV-A-1001",
                    "check_path": "/api/invoices/INV-A-1001",
                    "expect": {"status": 200, "json_field": "tenant_id", "equals": "owner_tenant"},
                }
            ],
            "identity_refs": {"actor": "tenant-b-dev", "owner": "tenant-a-owner"},
            "expected_authorized": {"status": 200, "contains_marker": "invoice_id"},
            "expected_unauthorized": {"denial_statuses": [403, 404]},
            "assertion": {
                "kind": "cross_tenant_document",
                "owner_marker_fixture": "invoice_id",
                "content_type": "application/pdf",
            },
        },
    )
    db.commit()

    from app.models import Finding

    bola = db.get(Finding, bola.id)
    release_c = _execute(
        db,
        _create(
            db,
            lab_project,
            settings,
            kind=RunKind.RELEASE_SCAN,
            build_label="2024.10.3",
            baseline=release_b,
        ),
        settings,
    )
    db.refresh(release_c)
    assert release_c.status == "completed"

    rows_b = comparison_findings(db, baseline, release_b)
    buckets_b = {row["public_id"]: row["bucket"] for row in rows_b}
    assert buckets_b[bola.public_id] == "fix_verified"
    assert buckets_b[export_finding.public_id] == "newly_observed"

    rows_c = comparison_findings(db, release_b, release_c)
    buckets_c = {row["public_id"]: row["bucket"] for row in rows_c}
    assert buckets_c[bola.public_id] == "regressed"
    assert buckets_c[export_finding.public_id] == "still_reproducible"
    assert bucket_counts(rows_c)["regressed"] == 1

    # The historical B snapshot still records the verified fix.
    b_state = state_for_build(db, bola.id, release_b.build_id, as_of=release_b.completed_at)
    assert b_state.outcome.value == "fix_verified"

    # A later retest on an older build cannot change the newer build's outcome.
    before = state_for_build(db, bola.id, release_c.build_id)
    late = db.query(Observation).filter_by(finding_id=bola.id, build_id=baseline.build_id).first()
    late.observed_at = datetime.now(UTC) + timedelta(days=1)
    db.commit()
    after = state_for_build(db, bola.id, release_c.build_id)
    assert before.outcome == after.outcome


def test_cancellation_before_discovery_skips_remaining_stages(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    job = db.get(Job, run.job_id)
    job.state = "cancel_requested"
    run.status = "cancel_requested"
    db.flush()
    execute_run(db, run=run, job=job, settings=settings)
    db.commit()
    db.refresh(run)
    assert run.status == "canceled"
    from app.models import RunStage

    stages = {stage.code: stage.state for stage in db.query(RunStage).filter_by(run_id=run.id)}
    assert stages["discovery"] == "canceled"
    assert stages["ingest"] == "canceled"
    assert db.query(Observation).filter_by(run_id=run.id).count() == 0


def test_revoked_membership_prevents_queued_execution(db, lab_project, settings):
    developer = lab_project.developer
    run = _create(
        db,
        lab_project,
        settings,
        kind=RunKind.BASELINE,
        build_label="2024.10.1",
        actor=developer,
    )
    membership = (
        db.query(ProjectMember)
        .filter_by(project_id=lab_project.project.id, user_id=developer.id)
        .one()
    )
    db.delete(membership)
    db.commit()
    job = _start(db, run)
    execute_run(db, run=run, job=job, settings=settings)
    db.commit()
    db.refresh(run)
    assert run.status == "failed"
    assert "no longer has access" in (run.failure_reason or "")
    assert db.query(Observation).filter_by(run_id=run.id).count() == 0


def test_narrowed_target_policy_prevents_dispatch(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    from app.models import TargetConfig

    narrowed = TargetConfig(
        project_id=lab_project.project.id,
        revision=2,
        base_url=lab_project.lab_base,
        allowed_origins=[lab_project.lab_base],
        path_prefixes=["/different"],
        environment_label="staging",
        run_limits={},
        created_by=lab_project.admin.id,
    )
    db.add(narrowed)
    db.commit()
    job = _start(db, run)
    execute_run(db, run=run, job=job, settings=settings)
    db.commit()
    db.refresh(run)
    assert run.status == "failed"
    assert "approved policy" in (run.failure_reason or "")


def test_duplicate_run_submission_returns_existing_run(db, lab_project, settings):
    first = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    second = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    assert first.id == second.id
    assert db.query(Run).filter_by(project_id=lab_project.project.id).count() == 1


def test_expired_worker_lease_becomes_interrupted_without_redispatch(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    job = db.get(Job, run.job_id)
    job.state = "running"
    job.claimed_by = "dead-worker"
    job.attempts = 1
    job.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)
    run.status = "running"
    db.commit()
    reconciled = reconcile(db, worker_id="new-worker")
    db.commit()
    db.refresh(job)
    db.refresh(run)
    assert "interrupted" in " ".join(reconciled)
    assert job.state == "interrupted"
    assert run.status == "interrupted"
    assert "Partial artifacts" in run.failure_reason
    # Interrupted work is not silently re-run.
    assert db.query(Job).filter_by(state="queued").count() == 0


def test_build_identity_mismatch_fails_run_before_discovery(db, lab_project, settings):
    run = _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1")
    build = db.get(Build, run.build_id)
    build.expected_identity = "2024.10.9"
    db.commit()
    job = _start(db, run)
    execute_run(db, run=run, job=job, settings=settings)
    db.commit()
    db.refresh(run)
    assert run.status == "failed"
    assert "build identity" in (run.failure_reason or "").lower()
    assert db.query(Observation).filter_by(run_id=run.id).count() == 0


def test_guided_and_weak_findings_stay_pending_in_release_scan(db, lab_project, settings):
    baseline = _execute(
        db,
        _create(db, lab_project, settings, kind=RunKind.BASELINE, build_label="2024.10.1"),
        settings,
    )
    plan = baseline.scope_snapshot
    assert plan is not None
    release = _execute(
        db,
        _create(
            db,
            lab_project,
            settings,
            kind=RunKind.RELEASE_SCAN,
            build_label="2024.10.2",
            baseline=baseline,
        ),
        settings,
    )
    db.refresh(release)
    release_plan = (release.scope_snapshot or {}).get("release_plan") or {}
    actions = {candidate["action"] for candidate in release_plan.get("candidates", [])}
    assert "guided_pending" in actions
    assert "skipped" in actions
    checks = db.query(RunCheck).filter_by(run_id=release.id).all()
    assert any(check.scenario_code == "pending-human-action" for check in checks)


def test_demo_fixture_writer_labels_synthetic_artifacts(tmp_path):
    target = demo.write_demo_artifacts(
        tmp_path,
        build_label=demo.BUILD_PATCHED,
        depth="quick",
        base_url="http://127.0.0.1:8099/deployments/2024.10.2",
        run_id="demo-run",
    )
    assert (target / "run.json").is_file()
    assert (target / "coverage.json").is_file()
    contract = (tmp_path / "strix_runs" / "demo-contract.json").read_text()
    assert "synthetic" in contract.lower()


_ = (make_finding,)
