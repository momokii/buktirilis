"""Persistent records for BuktiRilis.

Every ownership edge is explicit so queries can enforce project scope at the
boundary. Identifiers are UUIDs, times are stored in UTC, and stable project-level
finding IDs (``BR-12``) are separate from run-level provenance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_lookup", "email", "ip_hash", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ProjectMember(Base, TimestampMixin):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_member"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class TargetConfig(Base, TimestampMixin):
    """Immutable configuration revision for a project's approved staging scope."""

    __tablename__ = "target_configs"
    __table_args__ = (UniqueConstraint("project_id", "revision", name="uq_target_revision"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    allowed_origins: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    path_prefixes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    environment_label: Mapped[str] = mapped_column(String(80), default="staging", nullable=False)
    scope_owner: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    authorization_reference: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    run_limits: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class OpenApiDocument(Base, TimestampMixin):
    __tablename__ = "openapi_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_server_url: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    operations: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    sanitized_json: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Build(Base, TimestampMixin):
    __tablename__ = "builds"
    __table_args__ = (UniqueConstraint("project_id", "label", name="uq_build_label"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    target_url: Mapped[str] = mapped_column(String(512), nullable=False)
    target_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("target_configs.id"), nullable=False
    )
    openapi_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("openapi_documents.id")
    )
    commit_sha: Mapped[str | None] = mapped_column(String(80))
    build_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    expected_identity: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    identity_observed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    identity_attested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class TestAccount(Base, TimestampMixin):
    """Named test identity. The credential is encrypted with the deployment key."""

    __tablename__ = "test_accounts"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_account_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    role_label: Mapped[str] = mapped_column(String(60), nullable=False)
    tenant_label: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    credential_kind: Mapped[str] = mapped_column(String(20), default="bearer", nullable=False)
    credential_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    identity_check_path: Mapped[str] = mapped_column(String(200), default="/api/me", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Profile(Base, TimestampMixin):
    """Versioned testing plan. Selection states intent; coverage states what happened."""

    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_profile_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_claimable", "state", "available_at"),
        UniqueConstraint("idempotency_key", name="uq_job_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_project_created", "project_id", "created_at"),
        CheckConstraint(
            "status in ('queued','running','cancel_requested','completed','failed',"
            "'canceled','interrupted')",
            name="ck_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    build_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("builds.id"), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"))
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="demo", nullable=False)
    depth: Mapped[str] = mapped_column(String(20), nullable=False)
    profile_code: Mapped[str] = mapped_column(String(80), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    engine: Mapped[str] = mapped_column(String(40), default="strix", nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    runtime_image: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    config_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("target_configs.id"))
    scope_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    budget: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ingest_state: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    coverage_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    requested_by_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunStage(Base):
    __tablename__ = "run_stages"
    __table_args__ = (UniqueConstraint("run_id", "code", name="uq_run_stage"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_run", "run_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="info", nullable=False)
    code: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("project_id", "public_id", name="uq_finding_public_id"),
        Index("ix_findings_project_fingerprint", "project_id", "fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    public_id: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    issue_class: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_summary: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    actors_summary: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    impact: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expected_behavior: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observed_behavior: Mapped[str] = mapped_column(Text, default="", nullable=False)
    remediation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prerequisites: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    reproduction_steps: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    root_cause_hypothesis: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(30), default="supported", nullable=False)
    retest_method: Mapped[str] = mapped_column(String(30), default="guided", nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    disposition_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    first_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RunCheck(Base):
    """Execution record: one check tied to its run stage, scope, actor, and result."""

    __tablename__ = "run_checks"
    __table_args__ = (
        Index("ix_run_checks_run", "run_id"),
        UniqueConstraint("run_id", "check_key", name="uq_run_check_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("findings.id"))
    check_key: Mapped[str] = mapped_column(String(160), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    scenario_code: Mapped[str] = mapped_column(String(80), nullable=False)
    scenario_title: Mapped[str] = mapped_column(String(200), nullable=False)
    surface: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    actor_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    approach: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    coverage_source: Mapped[str] = mapped_column(String(40), default="engine", nullable=False)
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    result_detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owasp_refs: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Surface(Base, TimestampMixin):
    """Surface discovered during recon or supplied by a sanitized OpenAPI document."""

    __tablename__ = "surfaces"
    __table_args__ = (UniqueConstraint("run_id", "route", name="uq_surface_route"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    route: Mapped[str] = mapped_column(String(300), nullable=False)
    methods: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="recon", nullable=False)
    tested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Observation(Base):
    """Accepted, conclusively-scoped evidence for a finding on a build."""

    __tablename__ = "observations"
    __table_args__ = (Index("ix_observations_finding_build", "finding_id", "build_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    build_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("builds.id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("retest_attempts.id"))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recipe_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recipe_revisions.id"))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    reason_code: Mapped[str | None] = mapped_column(String(60))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_finding", "finding_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("findings.id"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("retest_attempts.id"))
    build_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("builds.id"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    attribution: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    highlight: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    actor_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    endpoint: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Recipe(Base, TimestampMixin):
    __tablename__ = "recipes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class RecipeRevision(Base):
    __tablename__ = "recipe_revisions"
    __table_args__ = (UniqueConstraint("recipe_id", "revision", name="uq_recipe_rev"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path_template: Mapped[str] = mapped_column(String(300), nullable=False)
    fixture_refs: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    identity_refs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    preconditions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    expected_unauthorized: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    expected_authorized: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    assertion: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RetestAttempt(Base):
    __tablename__ = "retest_attempts"
    __table_args__ = (Index("ix_attempts_finding_build", "finding_id", "build_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), nullable=False)
    build_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("builds.id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    recipe_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recipe_revisions.id"))
    recipe_revision_label: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(30))
    reason_code: Mapped[str | None] = mapped_column(String(60))
    reason_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    requested_by_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    build_identity_expected: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    build_identity_observed: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    prerequisites: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    positive_control: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    assertion_result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="demo", nullable=False)


class ManualReview(Base):
    __tablename__ = "manual_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retest_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ReadyMarker(Base):
    __tablename__ = "ready_markers"
    __table_args__ = (UniqueConstraint("finding_id", "build_id", name="uq_ready_marker"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), nullable=False)
    build_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("builds.id"), nullable=False)
    marked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ExportSnapshot(Base):
    __tablename__ = "export_snapshots"
    __table_args__ = (Index("ix_exports_run", "run_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="full", nullable=False)
    scope_detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="buktirilis.export.v1")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_project", "project_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64))


__all__ = [
    "Activity",
    "Artifact",
    "AuditEvent",
    "Base",
    "Build",
    "Evidence",
    "ExportSnapshot",
    "Finding",
    "Job",
    "LoginAttempt",
    "ManualReview",
    "Observation",
    "OpenApiDocument",
    "Profile",
    "Project",
    "ProjectMember",
    "ReadyMarker",
    "Recipe",
    "RecipeRevision",
    "RetestAttempt",
    "Run",
    "RunCheck",
    "RunStage",
    "Surface",
    "TargetConfig",
    "TestAccount",
    "User",
    "UserSession",
    "utcnow",
]
