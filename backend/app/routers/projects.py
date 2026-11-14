"""Projects, approved target policy, builds, test identities, and OpenAPI uploads."""

from __future__ import annotations

import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, ProjectAccess, get_principal, require_admin, require_project
from app.domain import AuditAction, Role
from app.models import (
    AuditEvent,
    Build,
    OpenApiDocument,
    Project,
    ProjectMember,
    TargetConfig,
    TestAccount,
    User,
)
from app.routers.deps import csrf_protected, current_target_config
from app.security import encrypt_secret, hash_password
from app.serializers import (
    account_row,
    build_row,
    iso,
    member_row,
    project_row,
    target_row,
)
from app.services.policy import (
    PolicyError,
    TargetPolicy,
    load_openapi_document,
    parse_origin,
    sanitise_openapi,
)
from app.services.retests import identity_attestation
from app.services.runs import surface_inventory

ROUTER = APIRouter(prefix="/projects", tags=["projects"])
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


class TargetInput(BaseModel):
    base_url: str = Field(min_length=8, max_length=512)
    allowed_origins: list[str] = []
    path_prefixes: list[str] = []
    environment_label: str = Field(default="staging", max_length=80)
    scope_owner: str = Field(default="", max_length=120)
    authorization_reference: str = Field(default="", max_length=160)
    run_limits: dict = {}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=2000)
    target: TargetInput


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class MemberCreate(BaseModel):
    user_id: uuid.UUID
    role: Role


class BuildCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    target_url: str = Field(min_length=8, max_length=512)
    commit_sha: str | None = Field(default=None, max_length=80)
    expected_identity: str | None = Field(default=None, max_length=160)
    build_metadata: dict = {}
    openapi_document_id: uuid.UUID | None = None


class AccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    role_label: str = Field(min_length=1, max_length=60)
    tenant_label: str = Field(default="", max_length=60)
    credential: str = Field(min_length=4, max_length=4096)
    identity_check_path: str = Field(default="/api/me", max_length=200)


class AccountRotate(BaseModel):
    credential: str = Field(min_length=4, max_length=4096)


class AttestationInput(BaseModel):
    observed_identity: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=400)


def _validate_target(payload: TargetInput) -> dict:
    origins = [
        origin.strip()
        for origin in (payload.allowed_origins or [payload.base_url])
        if origin.strip()
    ]
    if not origins:
        raise HTTPException(status_code=422, detail="At least one approved origin is required")
    for origin in origins:
        try:
            parse_origin(origin)
        except PolicyError as exc:
            raise HTTPException(status_code=422, detail=f"Approved origin rejected: {exc}") from exc
    try:
        base = parse_origin(payload.base_url)
    except PolicyError as exc:
        raise HTTPException(status_code=422, detail=f"Base URL rejected: {exc}") from exc
    base_origin = f"{base[0]}://{base[1]}:{base[2]}"
    if base_origin not in origins:
        raise HTTPException(status_code=422, detail="The base URL must match one approved origin")
    prefixes = []
    for prefix in payload.path_prefixes or []:
        value = str(prefix).strip()
        if not value.startswith("/") or ".." in value.split("/"):
            raise HTTPException(
                status_code=422, detail="Path restrictions must be absolute paths without '..'"
            )
        prefixes.append(value.rstrip("/") or "/")
    for key, value in (payload.run_limits or {}).items():
        if key not in {
            "max_depth",
            "max_runs_per_day",
            "max_budget_usd",
            "max_runtime_seconds",
            "max_replay_checks",
        }:
            raise HTTPException(status_code=422, detail=f"Unknown run limit {key!r}")
        if not isinstance(value, int | float | str):
            raise HTTPException(status_code=422, detail=f"Run limit {key!r} has an invalid value")
    if payload.run_limits.get("max_depth") and payload.run_limits["max_depth"] not in {
        "quick",
        "standard",
    }:
        raise HTTPException(status_code=422, detail="max_depth must be quick or standard")
    return {
        "base_url": payload.base_url.strip(),
        "allowed_origins": origins,
        "path_prefixes": prefixes,
        "environment_label": payload.environment_label.strip(),
        "scope_owner": payload.scope_owner.strip(),
        "authorization_reference": payload.authorization_reference.strip(),
        "run_limits": payload.run_limits,
    }


@ROUTER.get("")
def list_projects(
    db: Session = Depends(get_db), principal: Principal = Depends(get_principal)
) -> dict:
    if principal.user.is_admin:
        projects = list(db.execute(select(Project).order_by(Project.name)).scalars())
        rows = [project_row(db, project, "admin") for project in projects]
    else:
        memberships = {
            member.project_id: member.role
            for member in db.execute(
                select(ProjectMember).where(ProjectMember.user_id == principal.user.id)
            ).scalars()
        }
        projects = (
            list(
                db.execute(
                    select(Project).where(Project.id.in_(memberships.keys())).order_by(Project.name)
                ).scalars()
            )
            if memberships
            else []
        )
        rows = [project_row(db, project, memberships[project.id]) for project in projects]
    return {"items": rows}


@ROUTER.post("", status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    _: Principal = Depends(require_admin),
) -> dict:
    slug = (payload.slug or re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-"))[:60]
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(
            status_code=422,
            detail="Slug must be lowercase letters, digits, and hyphens (2-61 characters)",
        )
    if db.execute(select(Project).where(Project.slug == slug)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A project with this slug already exists")
    target = _validate_target(payload.target)
    project = Project(
        slug=slug,
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_by=principal.user.id,
    )
    db.add(project)
    db.flush()
    db.add(
        TargetConfig(
            project_id=project.id,
            revision=1,
            base_url=target["base_url"],
            allowed_origins=target["allowed_origins"],
            path_prefixes=target["path_prefixes"],
            environment_label=target["environment_label"],
            scope_owner=target["scope_owner"],
            authorization_reference=target["authorization_reference"],
            run_limits=target["run_limits"],
            created_by=principal.user.id,
        )
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=project.id,
            action=AuditAction.PROJECT_CREATED.value,
            target_type="project",
            target_id=str(project.id),
            metadata_json={"slug": slug, "origins": target["allowed_origins"]},
        )
    )
    db.commit()
    return project_row(db, project, "admin")


@ROUTER.get("/{project_id}")
def read_project(
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    project = access.project
    members = list(
        db.execute(select(ProjectMember).where(ProjectMember.project_id == project.id)).scalars()
    )
    builds = list(
        db.execute(
            select(Build).where(Build.project_id == project.id).order_by(Build.created_at.desc())
        ).scalars()
    )
    accounts = list(
        db.execute(
            select(TestAccount)
            .where(TestAccount.project_id == project.id)
            .order_by(TestAccount.name)
        ).scalars()
    )
    return {
        **project_row(db, project, access.role.value),
        "target_configs": [
            target_row(row)
            for row in db.execute(
                select(TargetConfig)
                .where(TargetConfig.project_id == project.id)
                .order_by(TargetConfig.revision.desc())
            ).scalars()
        ],
        "members": [member_row(db, member) for member in members],
        "builds": [build_row(db, build) for build in builds],
        "accounts": [account_row(account) for account in accounts],
        "capabilities": {
            "can_admin": access.is_admin,
            "can_operate": access.can(Role.OPERATOR),
            "can_develop": access.can(Role.DEVELOPER),
            "can_export": access.can(Role.VIEWER),
        },
        "profiles": [
            {
                "code": "web-api-access-control",
                "version": 1,
                "name": "Web & API Access Control",
                "surfaces": sorted(
                    {
                        surface["route"]
                        for build in builds
                        for surface in surface_inventory(db, build, "web-api-access-control", 1)
                    }
                ),
            }
        ],
        "environment": get_settings().app_env,
    }


@ROUTER.patch("/{project_id}")
def update_project(
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(
            status_code=403, detail="Only an administrator can change project settings"
        )
    project = access.project
    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description.strip()
    db.commit()
    return project_row(db, project, "admin")


@ROUTER.post("/{project_id}/target-configs", status_code=201)
def create_target_config(
    payload: TargetInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(
            status_code=403, detail="Only an administrator can change target policy"
        )
    target = _validate_target(payload)
    latest = current_target_config(db, access.project)
    revision = (latest.revision if latest else 0) + 1
    config = TargetConfig(
        project_id=access.project.id,
        revision=revision,
        base_url=target["base_url"],
        allowed_origins=target["allowed_origins"],
        path_prefixes=target["path_prefixes"],
        environment_label=target["environment_label"],
        scope_owner=target["scope_owner"],
        authorization_reference=target["authorization_reference"],
        run_limits=target["run_limits"],
        created_by=principal.user.id,
    )
    db.add(config)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.TARGET_CONFIG_CREATED.value,
            target_type="target_config",
            target_id=str(config.id),
            metadata_json={"revision": revision, "origins": target["allowed_origins"]},
        )
    )
    db.commit()
    return target_row(config)


@ROUTER.post("/{project_id}/members", status_code=201)
def add_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(status_code=403, detail="Only an administrator can manage membership")
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == access.project.id,
            ProjectMember.user_id == payload.user_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.role = payload.role.value
        db.commit()
        return member_row(db, existing)
    member = ProjectMember(
        project_id=access.project.id,
        user_id=payload.user_id,
        role=payload.role.value,
        added_by=principal.user.id,
    )
    db.add(member)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.MEMBER_ADDED.value,
            target_type="user",
            target_id=str(payload.user_id),
            metadata_json={"role": payload.role.value},
        )
    )
    db.commit()
    return member_row(db, member)


@ROUTER.delete("/{project_id}/members/{user_id}")
def remove_member(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(status_code=403, detail="Only an administrator can manage membership")
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == access.project.id, ProjectMember.user_id == user_id
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(member)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.MEMBER_REMOVED.value,
            target_type="user",
            target_id=str(user_id),
            metadata_json={},
        )
    )
    db.commit()
    return {"ok": True}


@ROUTER.get("/{project_id}/builds")
def list_builds(
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    builds = list(
        db.execute(
            select(Build)
            .where(Build.project_id == access.project.id)
            .order_by(Build.created_at.desc())
        ).scalars()
    )
    return {"items": [build_row(db, build) for build in builds]}


@ROUTER.post("/{project_id}/builds", status_code=201)
def create_build(
    payload: BuildCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.can(Role.OPERATOR):
        raise HTTPException(status_code=403, detail="Operator role required to register builds")
    config = current_target_config(db, access.project)
    if config is None:
        raise HTTPException(
            status_code=409, detail="Approve a target policy before registering a build"
        )
    policy = TargetPolicy.from_config(
        config, allow_loopback=bool(get_settings().allow_loopback_lab_targets)
    )
    try:
        policy.check(payload.target_url)
    except PolicyError as exc:
        raise HTTPException(status_code=422, detail=f"Build target rejected: {exc}") from exc
    label = payload.label.strip()
    if db.execute(
        select(Build).where(Build.project_id == access.project.id, Build.label == label)
    ).scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="A build with this label already exists; use a new label for a redeploy",
        )
    document = None
    if payload.openapi_document_id:
        document = db.get(OpenApiDocument, payload.openapi_document_id)
        if document is None or document.project_id != access.project.id:
            raise HTTPException(
                status_code=404, detail="OpenAPI revision not found in this project"
            )
    build = Build(
        project_id=access.project.id,
        label=label,
        target_url=payload.target_url.strip(),
        target_config_id=config.id,
        openapi_document_id=payload.openapi_document_id,
        commit_sha=(payload.commit_sha or "").strip() or None,
        build_metadata=payload.build_metadata,
        expected_identity=(payload.expected_identity or "").strip(),
        identity_observed=False,
        created_by=principal.user.id,
    )
    db.add(build)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.BUILD_CREATED.value,
            target_type="build",
            target_id=str(build.id),
            metadata_json={
                "label": label,
                "target_url": build.target_url,
                "expected_identity": build.expected_identity,
                "openapi_document_id": str(document.id) if document else None,
            },
        )
    )
    db.commit()
    return build_row(db, build)


@ROUTER.post("/{project_id}/builds/{build_id}/attest")
def attest_build(
    build_id: uuid.UUID,
    payload: AttestationInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    build = db.get(Build, build_id)
    if build is None or build.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Build not found")
    identity_attestation(
        db,
        build=build,
        actor=principal.user,
        observed_identity=payload.observed_identity,
        note=payload.note,
    )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.BUILD_IDENTITY_ATTESTED.value,
            target_type="build",
            target_id=str(build.id),
            metadata_json={"identity": build.expected_identity},
        )
    )
    db.commit()
    return build_row(db, build)


@ROUTER.get("/{project_id}/accounts")
def list_accounts(
    access: ProjectAccess = Depends(require_project(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> dict:
    accounts = list(
        db.execute(
            select(TestAccount)
            .where(TestAccount.project_id == access.project.id)
            .order_by(TestAccount.name)
        ).scalars()
    )
    return {"items": [account_row(account) for account in accounts]}


@ROUTER.post("/{project_id}/accounts", status_code=201)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(
            status_code=403, detail="Only an administrator can manage test credentials"
        )
    if db.execute(
        select(TestAccount).where(
            TestAccount.project_id == access.project.id, TestAccount.name == payload.name.strip()
        )
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A test identity with this name already exists")
    account = TestAccount(
        project_id=access.project.id,
        name=payload.name.strip(),
        role_label=payload.role_label.strip(),
        tenant_label=payload.tenant_label.strip(),
        credential_ciphertext=encrypt_secret(payload.credential),
        identity_check_path=payload.identity_check_path,
        created_by=principal.user.id,
    )
    db.add(account)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.ACCOUNT_CREATED.value,
            target_type="test_account",
            target_id=str(account.id),
            metadata_json={"name": account.name, "tenant": account.tenant_label},
        )
    )
    db.commit()
    return account_row(account)


@ROUTER.patch("/{project_id}/accounts/{account_id}/credential")
def rotate_account_credential(
    account_id: uuid.UUID,
    payload: AccountRotate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(
            status_code=403, detail="Only an administrator can rotate test credentials"
        )
    account = db.get(TestAccount, account_id)
    if account is None or account.project_id != access.project.id:
        raise HTTPException(status_code=404, detail="Test identity not found")
    account.credential_ciphertext = encrypt_secret(payload.credential)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action="project.test_credential_rotated",
            target_type="test_account",
            target_id=str(account.id),
            metadata_json={"name": account.name, "queued_jobs_note": "resolved at execution time"},
        )
    )
    db.commit()
    return account_row(account)


@ROUTER.get("/{project_id}/audit")
def project_audit(
    limit: int = 50,
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> dict:
    rows = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.project_id == access.project.id)
            .order_by(AuditEvent.at.desc())
            .limit(min(max(limit, 1), 200))
        ).scalars()
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "at": iso(row.at),
                "actor": row.actor_label,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "metadata": row.metadata_json,
            }
            for row in rows
        ]
    }


@ROUTER.post("/{project_id}/openapi", status_code=201)
async def upload_openapi(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
    access: ProjectAccess = Depends(require_project(Role.OPERATOR)),
) -> dict:
    if not access.is_admin:
        raise HTTPException(status_code=403, detail="Only an administrator can approve an API spec")
    settings = get_settings()
    raw = await file.read(settings.max_openapi_bytes + 1)
    if len(raw) > settings.max_openapi_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"OpenAPI document exceeds the {settings.max_openapi_bytes} byte limit",
        )
    config = current_target_config(db, access.project)
    if config is None:
        raise HTTPException(
            status_code=409, detail="Approve a target policy before uploading a spec"
        )
    policy = TargetPolicy.from_config(
        config, allow_loopback=bool(settings.allow_loopback_lab_targets)
    )
    try:
        document = load_openapi_document(raw, file.filename or "spec.json")
        sanitised, declared_urls, operations = sanitise_openapi(document, policy)
    except PolicyError as exc:
        raise HTTPException(status_code=422, detail=f"OpenAPI upload rejected: {exc}") from exc
    record = OpenApiDocument(
        project_id=access.project.id,
        filename=(file.filename or "openapi.json")[:200],
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        declared_server_url=", ".join(declared_urls)[:512],
        operations=operations,
        sanitized_json=sanitised,
        created_by=principal.user.id,
    )
    db.add(record)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=access.project.id,
            action=AuditAction.OPENAPI_UPLOADED.value,
            target_type="openapi_document",
            target_id=str(record.id),
            metadata_json={
                "filename": record.filename,
                "operations": len(operations),
                "declared_servers": declared_urls,
            },
        )
    )
    db.commit()
    return {
        "id": str(record.id),
        "filename": record.filename,
        "sha256": record.sha256,
        "operations": operations,
        "declared_server_url": record.declared_server_url,
        "created_at": iso(record.created_at),
    }


_ = (hash_password,)
