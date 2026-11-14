"""Test helpers for building findings, recipes, and runs."""

from __future__ import annotations

from app.domain import RunKind, RunStatus
from app.models import Finding, Observation, Recipe, Run, User
from app.security import hash_password
from app.services.findings import compute_fingerprint
from app.services.recipes import create_recipe_revision


def make_user(db, email: str, *, admin: bool = False, name: str | None = None) -> User:
    user = User(
        email=email,
        display_name=name or email.split("@")[0].title(),
        password_hash=hash_password("correct horse battery staple"),
        is_admin=admin,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def make_finding(
    db,
    project,
    *,
    title="Cross-tenant invoice read",
    issue_class="broken-object-authorization",
    severity="high",
    scope="GET /api/invoices/{invoice_id}",
    actors="tenant-b developer → tenant-a invoice",
    evidence_status="supported",
) -> Finding:
    fingerprint = compute_fingerprint(
        issue_class=issue_class, scope=scope, actor_boundary=actors, condition="tenant mismatch"
    )
    existing = (
        db.query(Finding)
        .filter(Finding.project_id == project.id, Finding.fingerprint == fingerprint)
        .one_or_none()
    )
    if existing is not None:
        return existing
    count = db.query(Finding).filter(Finding.project_id == project.id).count()
    finding = Finding(
        project_id=project.id,
        public_id=f"BR-{count + 1}",
        title=title,
        severity=severity,
        issue_class=issue_class,
        scope_summary=scope,
        actors_summary=actors,
        impact="Tenant data disclosure.",
        expected_behavior="Denied for other tenants.",
        observed_behavior="Returned to another tenant.",
        remediation="Scope the query by tenant.",
        prerequisites=["Two identities"],
        reproduction_steps=["Request the object as the other tenant"],
        fingerprint=fingerprint,
        evidence_status=evidence_status,
        retest_method="automatic",
    )
    db.add(finding)
    db.flush()
    return finding


BOLA_RECIPE = {
    "method": "GET",
    "path_template": "/api/invoices/{invoice_id}",
    "fixture_refs": [
        {
            "name": "invoice_id",
            "value": "INV-A-1001",
            "check_path": "/api/invoices/INV-A-1001",
            "expect": {"status": 200, "json_field": "tenant_id", "equals": "owner_tenant"},
        }
    ],
    "identity_refs": {"actor": "tenant-b-dev", "owner": "tenant-a-owner"},
    "expected_authorized": {"status": 200, "json_field": "tenant_id", "equals_identity_tenant": True},
    "expected_unauthorized": {
        "statuses": [200],
        "denial_statuses": [403, 404],
        "denial_error_field": "error.code",
        "denial_error_prefix": "TENANT_",
    },
    "assertion": {
        "kind": "cross_tenant_json_object",
        "owner_field": "tenant_id",
        "highlight_fields": ["tenant_id", "invoice_id", "total_cents"],
    },
}

EXPORT_RECIPE = {
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
    "expected_unauthorized": {
        "statuses": [200],
        "denial_statuses": [403, 404],
        "denial_error_field": "error.code",
        "denial_error_prefix": "TENANT_",
    },
    "assertion": {
        "kind": "cross_tenant_document",
        "owner_marker_fixture": "invoice_id",
        "content_type": "application/pdf",
    },
}


def approve_recipe(db, project, finding, actor, payload: dict | None = None) -> Recipe:
    payload = dict(payload or BOLA_RECIPE)
    recipe, revision = create_recipe_revision(
        db, project=project, finding=finding, payload=payload, actor=actor, approve=True
    )
    db.commit()
    return recipe


def make_run(db, project, build, actor, *, kind=RunKind.BASELINE, status=RunStatus.COMPLETED, when=None) -> Run:
    from app.models import utcnow

    run = Run(
        project_id=project.id,
        build_id=build.id,
        kind=kind.value,
        mode="demo",
        depth="quick",
        profile_code="web-api-access-control",
        profile_version=1,
        status=status.value,
        requested_by=actor.id,
        requested_by_label=actor.display_name,
        started_at=when or utcnow(),
        completed_at=(when or utcnow()) if status == RunStatus.COMPLETED else None,
        snapshot_at=(when or utcnow()) if status == RunStatus.COMPLETED else None,
        scope_snapshot={"base_url": build.target_url},
        budget={"max_checks": 10},
    )
    db.add(run)
    db.flush()
    return run


def add_observation(
    db, finding, build, *, outcome: str, observed_at, source="engine", run=None, stale=False
) -> Observation:
    build_id = build if isinstance(build, __import__("uuid").UUID) else build.id
    observation = Observation(
        project_id=finding.project_id,
        finding_id=finding.id,
        build_id=build_id,
        run_id=run.id if run else None,
        source=source,
        outcome=outcome,
        accepted=True,
        observed_at=observed_at,
        detail={"stale": stale} if stale else {},
    )
    db.add(observation)
    db.flush()
    return observation
