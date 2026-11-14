"""Reproducible demo dataset: users, project, approved scope, builds, runs, and recipes.

The seed executes the real pipeline (including real constrained replays against the
bundled lab). It is idempotent: an existing project is reported and left untouched.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import RunKind
from app.models import (
    AuditEvent,
    Build,
    Finding,
    Job,
    OpenApiDocument,
    Profile,
    Project,
    ProjectMember,
    Run,
    TargetConfig,
    TestAccount,
    User,
)
from app.security import encrypt_secret, hash_password
from app.services import demo
from app.services.pipeline import execute_run
from app.services.profiles import list_profiles
from app.services.recipes import create_recipe_revision
from app.services.runs import create_run

DEMO_PROJECT_SLUG = "atlas-billing"
DEMO_USERS = {
    "operator": "operator@demo.buktirilis.local",
    "developer": "developer@demo.buktirilis.local",
    "viewer": "viewer@demo.buktirilis.local",
}
DEMO_ACCOUNTS = [
    ("tenant-a-owner", "owner", "tenant-a", "lab.tenant-a-owner"),
    ("tenant-a-approver", "approver", "tenant-a", "lab.tenant-a-approver"),
    ("tenant-b-dev", "developer", "tenant-b", "lab.tenant-b-dev"),
    ("tenant-b-approver", "approver", "tenant-b", "lab.tenant-b-approver"),
    ("tenant-b-expired", "developer", "tenant-b", "lab.tenant-b-expired"),
    ("tenant-c-observer", "viewer", "tenant-c", "lab.tenant-c-observer"),
]


def sync_profiles(db: Session) -> None:
    for profile in list_profiles():
        existing = db.execute(
            select(Profile).where(Profile.code == profile.code, Profile.version == profile.version)
        ).scalar_one_or_none()
        config_payload: dict[str, Any] = {
            "scenarios": [scenario.code for scenario in profile.scenarios],
            "reference_links": list(profile.reference_links),
        }
        if existing is None:
            db.add(
                Profile(
                    code=profile.code,
                    version=profile.version,
                    name=profile.name,
                    description=profile.description,
                    status="active",
                    config=config_payload,
                )
            )
        else:
            existing.config = config_payload
            existing.description = profile.description
    db.flush()


def _demo_password() -> str:
    return secrets.token_urlsafe(18)


def _write_credentials(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _demo_openapi(origin: str, *, with_export: bool) -> dict:
    paths = {
        "/api/invoices": {
            "get": {
                "operationId": "listInvoices",
                "summary": "List invoices for the caller's tenant",
                "responses": {"200": {"description": "Invoice list"}},
            }
        },
        "/api/invoices/{invoice_id}": {
            "get": {
                "operationId": "getInvoice",
                "summary": "Read one invoice",
                "parameters": [
                    {
                        "name": "invoice_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "Invoice"}, "403": {"description": "Denied"}},
            }
        },
        "/api/approvals/{invoice_id}": {
            "post": {
                "operationId": "createApproval",
                "summary": "Submit an approval request",
                "responses": {"200": {"description": "Approval request"}},
            }
        },
    }
    if with_export:
        paths["/api/exports/{invoice_id}/pdf"] = {
            "get": {
                "operationId": "exportInvoice",
                "summary": "Export an invoice PDF",
                "responses": {
                    "200": {"description": "PDF document"},
                    "403": {"description": "Denied"},
                },
            }
        }
    return {
        "openapi": "3.0.3",
        "info": {"title": "Atlas Billing API", "version": "1.0.0"},
        "servers": [{"url": origin}],
        "paths": paths,
    }


def _store_spec(
    db: Session, project: Project, origin: str, *, with_export: bool, revision: str, actor: User
) -> OpenApiDocument:
    from app.services.policy import sanitise_openapi

    config = db.execute(
        select(TargetConfig)
        .where(TargetConfig.project_id == project.id)
        .order_by(TargetConfig.revision.desc())
        .limit(1)
    ).scalar_one()
    from app.config import get_settings
    from app.services.policy import TargetPolicy

    policy = TargetPolicy.from_config(
        config, allow_loopback=bool(get_settings().allow_loopback_lab_targets)
    )
    document = _demo_openapi(origin, with_export=with_export)
    sanitised, declared, operations = sanitise_openapi(document, policy)
    record = OpenApiDocument(
        project_id=project.id,
        filename=f"atlas-billing-{revision}.json",
        sha256=__import__("hashlib").sha256(json.dumps(document).encode()).hexdigest(),
        size_bytes=len(json.dumps(document).encode()),
        declared_server_url=", ".join(declared),
        operations=operations,
        sanitized_json=sanitised,
        created_by=actor.id,
    )
    db.add(record)
    db.flush()
    return record


def _run_now(db: Session, *, run: Run, settings: Settings, worker: str = "seed") -> Run:
    job = db.get(Job, run.job_id)
    if job is None:
        raise RuntimeError("seed run has no job")
    job.state = "running"
    job.claimed_by = worker
    job.attempts = 1
    job.started_at = datetime.now(UTC)
    db.flush()
    execute_run(db, run=run, job=job, settings=settings)
    db.flush()
    return run


def _approved_offer_recipe(
    db: Session,
    *,
    project: Project,
    finding: Finding,
    actor: User,
    path_template: str,
    fixture_name: str,
    fixture_value: str,
    check_path: str,
    assertion: dict,
    expected_authorized: dict,
) -> None:
    payload = {
        "method": "GET",
        "path_template": path_template,
        "fixture_refs": [
            {
                "name": fixture_name,
                "value": fixture_value,
                "check_path": check_path,
                "expect": {"status": 200, "json_field": "tenant_id", "equals": "owner_tenant"},
            }
        ],
        "identity_refs": {"actor": "tenant-b-dev", "owner": "tenant-a-owner"},
        "expected_authorized": expected_authorized,
        "expected_unauthorized": {
            "statuses": [200],
            "denial_statuses": [403, 404],
            "denial_error_field": "error.code",
            "denial_error_prefix": "TENANT_",
        },
        "assertion": assertion,
        "preconditions": [
            "build_identity",
            "actor_identity",
            "fixture_present",
            "positive_control",
        ],
    }
    create_recipe_revision(
        db, project=project, finding=finding, payload=payload, actor=actor, approve=True
    )


def seed_demo(
    db: Session,
    *,
    settings: Settings,
    admin_email: str | None = None,
    credentials_path: Path | None = None,
) -> dict:
    if not settings.demo_enabled:
        raise RuntimeError("Demo seeding requires DEMO_SEED_ENABLED (or APP_ENV=development)")
    existing = db.execute(
        select(Project).where(Project.slug == DEMO_PROJECT_SLUG)
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "already_seeded": True,
            "project_id": str(existing.id),
            "message": "The demo project already exists; no changes were made.",
        }

    sync_profiles(db)
    origin = settings.lab_base_url.rstrip("/")
    credentials: list[str] = []

    admin = None
    if admin_email:
        admin = db.execute(
            select(User).where(User.email == admin_email.strip().lower())
        ).scalar_one_or_none()
    if admin is None:
        admin = db.execute(
            select(User).where(User.is_admin.is_(True)).limit(1)
        ).scalar_one_or_none()
    if admin is None:
        password = _demo_password()
        admin = User(
            email=(admin_email or "admin@demo.buktirilis.local").lower(),
            display_name="Installation Admin",
            password_hash=hash_password(password),
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        credentials.append(f"admin {admin.email} {password}")

    users: dict[str, User] = {"admin": admin}
    for role, email in DEMO_USERS.items():
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            password = _demo_password()
            user = User(
                email=email,
                display_name=f"Demo {role.title()}",
                password_hash=hash_password(password),
                is_admin=False,
                is_active=True,
            )
            db.add(user)
            db.flush()
            credentials.append(f"{role} {email} {password}")
        users[role] = user

    project = Project(
        slug=DEMO_PROJECT_SLUG,
        name="Atlas Billing",
        description=(
            "Internal billing API on staging. Synthetic data only; used for the reproducible "
            "BuktiRilis demo."
        ),
        created_by=admin.id,
    )
    db.add(project)
    db.flush()
    for role, user in users.items():
        if role == "admin":
            continue
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=user.id,
                role=role if role in {"operator", "developer", "viewer"} else "viewer",
                added_by=admin.id,
            )
        )
    config = TargetConfig(
        project_id=project.id,
        revision=1,
        base_url=origin,
        allowed_origins=[origin],
        path_prefixes=["/deployments"],
        environment_label="staging",
        scope_owner="Platform Security",
        authorization_reference="DEMO-AUTH-ATLAS-001",
        run_limits={
            "max_depth": "standard",
            "max_runs_per_day": 20,
            "max_budget_usd": 5.0,
            "max_runtime_seconds": 1800,
            "max_replay_checks": 12,
        },
        created_by=admin.id,
    )
    db.add(config)
    db.flush()

    for name, role, tenant, token in DEMO_ACCOUNTS:
        db.add(
            TestAccount(
                project_id=project.id,
                name=name,
                role_label=role,
                tenant_label=tenant,
                credential_ciphertext=encrypt_secret(token),
                created_by=admin.id,
            )
        )
    db.flush()

    spec_v1 = _store_spec(db, project, origin, with_export=False, revision="v1", actor=admin)
    spec_v2 = _store_spec(db, project, origin, with_export=True, revision="v2", actor=admin)

    builds: dict[str, Build] = {}
    for label in demo.DEMO_BUILDS:
        document = spec_v1 if label == demo.BUILD_VULNERABLE else spec_v2
        build = Build(
            project_id=project.id,
            label=label,
            target_url=f"{origin}/deployments/{label}",
            target_config_id=config.id,
            openapi_document_id=document.id,
            commit_sha=f"demo-{label.replace('.', '-')}",
            build_metadata={"source": "demo", "synthetic": True},
            expected_identity=label,
            identity_observed=False,
            created_by=admin.id,
        )
        db.add(build)
        builds[label] = build
    hotfix = Build(
        project_id=project.id,
        label=f"{demo.BUILD_VULNERABLE}-hotfix",
        target_url=f"{origin}/deployments/{demo.BUILD_VULNERABLE}",
        target_config_id=config.id,
        openapi_document_id=spec_v1.id,
        commit_sha="demo-hotfix",
        build_metadata={
            "source": "demo",
            "synthetic": True,
            "note": "Deliberate identity mismatch used to demonstrate inconclusive handling.",
        },
        expected_identity=f"{demo.BUILD_VULNERABLE}-hotfix",
        identity_observed=False,
        created_by=admin.id,
    )
    db.add(hotfix)
    db.flush()

    operator = users["operator"]
    baseline_run, _ = create_run(
        db,
        settings=settings,
        project=project,
        build=builds[demo.BUILD_VULNERABLE],
        kind=RunKind.BASELINE.value,
        depth="quick",
        profile_code="web-api-access-control",
        profile_version=1,
        account_ids=[
            account.id
            for account in db.execute(
                select(TestAccount).where(TestAccount.project_id == project.id)
            ).scalars()
            if account.name in {"tenant-a-owner", "tenant-b-dev"}
        ],
        unauthenticated=False,
        baseline_run_id=None,
        actor=operator,
        accept_reduced_scope=True,
    )
    db.commit()
    baseline_run = _run_now(db, run=baseline_run, settings=settings)
    db.commit()

    bola = db.execute(
        select(Finding).where(
            Finding.project_id == project.id, Finding.issue_class == "broken-object-authorization"
        )
    ).scalar_one()
    _approved_offer_recipe(
        db,
        project=project,
        finding=bola,
        actor=operator,
        path_template="/api/invoices/{invoice_id}",
        fixture_name="invoice_id",
        fixture_value="INV-A-1001",
        check_path="/api/invoices/INV-A-1001",
        assertion={
            "kind": "cross_tenant_json_object",
            "owner_field": "tenant_id",
            "highlight_fields": ["tenant_id", "invoice_id", "total_cents"],
        },
        expected_authorized={
            "status": 200,
            "json_field": "tenant_id",
            "equals_identity_tenant": True,
        },
    )
    db.commit()

    release_b, _ = create_run(
        db,
        settings=settings,
        project=project,
        build=builds[demo.BUILD_PATCHED],
        kind=RunKind.RELEASE_SCAN.value,
        depth="standard",
        profile_code="web-api-access-control",
        profile_version=1,
        account_ids=[
            account.id
            for account in db.execute(
                select(TestAccount).where(TestAccount.project_id == project.id)
            ).scalars()
            if account.name in {"tenant-a-owner", "tenant-b-dev"}
        ],
        unauthenticated=False,
        baseline_run_id=baseline_run.id,
        actor=operator,
        accept_reduced_scope=True,
    )
    db.commit()
    release_b = _run_now(db, run=release_b, settings=settings)
    db.commit()

    export_finding = db.execute(
        select(Finding).where(
            Finding.project_id == project.id, Finding.issue_class == "cross-tenant-export"
        )
    ).scalar_one()
    _approved_offer_recipe(
        db,
        project=project,
        finding=export_finding,
        actor=operator,
        path_template="/api/exports/{invoice_id}/pdf",
        fixture_name="invoice_id",
        fixture_value="INV-A-1001",
        check_path="/api/invoices/INV-A-1001",
        assertion={
            "kind": "cross_tenant_document",
            "owner_marker_fixture": "invoice_id",
            "content_type": "application/pdf",
        },
        expected_authorized={"status": 200, "contains_marker": "invoice_id"},
    )
    db.commit()

    release_c, _ = create_run(
        db,
        settings=settings,
        project=project,
        build=builds[demo.BUILD_REGRESSED],
        kind=RunKind.RELEASE_SCAN.value,
        depth="standard",
        profile_code="web-api-access-control",
        profile_version=1,
        account_ids=[
            account.id
            for account in db.execute(
                select(TestAccount).where(TestAccount.project_id == project.id)
            ).scalars()
            if account.name in {"tenant-a-owner", "tenant-b-dev"}
        ],
        unauthenticated=False,
        baseline_run_id=release_b.id,
        actor=operator,
        accept_reduced_scope=True,
    )
    db.commit()
    release_c = _run_now(db, run=release_c, settings=settings)
    db.commit()

    from app.services.exports import create_export

    for fmt in ("json", "csv", "pdf"):
        create_export(db, project=project, run=release_c, fmt=fmt, actor=operator)
    db.add(
        AuditEvent(
            actor_id=operator.id,
            actor_label=operator.label if hasattr(operator, "label") else operator.display_name,
            project_id=project.id,
            action="demo.seeded",
            target_type="project",
            target_id=str(project.id),
            metadata_json={
                "builds": [build.label for build in builds.values()],
                "runs": [str(baseline_run.id), str(release_b.id), str(release_c.id)],
                "synthetic": True,
            },
        )
    )
    db.flush()

    if credentials_path is not None and credentials:
        _write_credentials(credentials_path, credentials)
    return {
        "already_seeded": False,
        "project_id": str(project.id),
        "project_slug": project.slug,
        "builds": [build.label for build in builds.values()],
        "runs": {
            "baseline": str(baseline_run.id),
            "patched": str(release_b.id),
            "regressed": str(release_c.id),
        },
        "users": {role: user.email for role, user in users.items()},
        "credentials_written": bool(credentials_path and credentials),
        "credentials_path": str(credentials_path) if credentials_path and credentials else "",
        "demo_mode": settings.demo_enabled,
        "variants": {
            "identity_mismatch_build": hotfix.label,
            "expired_identity": "tenant-b-expired",
            "wrong_tenant_owner": "tenant-c-observer",
        },
    }


def credentials_file() -> Path:
    """Default to the repository-level var/ directory regardless of the caller's cwd."""
    default = Path(__file__).resolve().parents[3] / "var"
    root = Path(os.environ.get("BUKTIRILIS_VAR_DIR", str(default)))
    return (root / "demo-credentials.txt").resolve()


_ = (uuid,)
