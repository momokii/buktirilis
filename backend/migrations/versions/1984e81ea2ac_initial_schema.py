"""initial schema

Revision ID: 1984e81ea2ac
Revises: 
Create Date: 2026-11-14 21:24:49.640661
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '1984e81ea2ac'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('login_attempts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('ip_hash', sa.String(length=64), nullable=False),
    sa.Column('succeeded', sa.Boolean(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_login_attempts_lookup', 'login_attempts', ['email', 'ip_hash', 'at'], unique=False)
    op.create_table('profiles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', 'version', name='uq_profile_version')
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('display_name', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('projects',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('user_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('user_agent_hash', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_table('artifacts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('storage_key', sa.String(length=300), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('content_type', sa.String(length=120), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_artifacts_project_id'), 'artifacts', ['project_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('actor_label', sa.String(length=200), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('target_type', sa.String(length=60), nullable=False),
    sa.Column('target_id', sa.String(length=120), nullable=False),
    sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_events_project', 'audit_events', ['project_id', 'at'], unique=False)
    op.create_table('openapi_documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('declared_server_url', sa.String(length=512), nullable=False),
    sa.Column('operations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('sanitized_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_openapi_documents_project_id'), 'openapi_documents', ['project_id'], unique=False)
    op.create_table('project_members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('added_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['added_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'user_id', name='uq_member')
    )
    op.create_index(op.f('ix_project_members_project_id'), 'project_members', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_members_user_id'), 'project_members', ['user_id'], unique=False)
    op.create_table('target_configs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('base_url', sa.String(length=512), nullable=False),
    sa.Column('allowed_origins', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('path_prefixes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('environment_label', sa.String(length=80), nullable=False),
    sa.Column('scope_owner', sa.String(length=120), nullable=False),
    sa.Column('authorization_reference', sa.String(length=160), nullable=False),
    sa.Column('run_limits', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'revision', name='uq_target_revision')
    )
    op.create_index(op.f('ix_target_configs_project_id'), 'target_configs', ['project_id'], unique=False)
    op.create_table('test_accounts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('role_label', sa.String(length=60), nullable=False),
    sa.Column('tenant_label', sa.String(length=60), nullable=False),
    sa.Column('credential_kind', sa.String(length=20), nullable=False),
    sa.Column('credential_ciphertext', sa.Text(), nullable=False),
    sa.Column('identity_check_path', sa.String(length=200), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'name', name='uq_account_name')
    )
    op.create_index(op.f('ix_test_accounts_project_id'), 'test_accounts', ['project_id'], unique=False)
    op.create_table('builds',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('label', sa.String(length=120), nullable=False),
    sa.Column('target_url', sa.String(length=512), nullable=False),
    sa.Column('target_config_id', sa.Uuid(), nullable=False),
    sa.Column('openapi_document_id', sa.Uuid(), nullable=True),
    sa.Column('commit_sha', sa.String(length=80), nullable=True),
    sa.Column('build_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('expected_identity', sa.String(length=160), nullable=False),
    sa.Column('identity_observed', sa.Boolean(), nullable=False),
    sa.Column('identity_attested_by', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['identity_attested_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['openapi_document_id'], ['openapi_documents.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_config_id'], ['target_configs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'label', name='uq_build_label')
    )
    op.create_index(op.f('ix_builds_project_id'), 'builds', ['project_id'], unique=False)
    op.create_table('jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('state', sa.String(length=30), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('claimed_by', sa.String(length=120), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('requested_by', sa.Uuid(), nullable=True),
    sa.Column('idempotency_key', sa.String(length=160), nullable=True),
    sa.Column('error_code', sa.String(length=80), nullable=True),
    sa.Column('error_detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key', name='uq_job_idempotency')
    )
    op.create_index('ix_jobs_claimable', 'jobs', ['state', 'available_at'], unique=False)
    op.create_index(op.f('ix_jobs_project_id'), 'jobs', ['project_id'], unique=False)
    op.create_table('runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('build_id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('baseline_run_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('depth', sa.String(length=20), nullable=False),
    sa.Column('profile_code', sa.String(length=80), nullable=False),
    sa.Column('profile_version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('engine', sa.String(length=40), nullable=False),
    sa.Column('engine_version', sa.String(length=40), nullable=False),
    sa.Column('runtime_image', sa.String(length=200), nullable=False),
    sa.Column('config_revision_id', sa.Uuid(), nullable=True),
    sa.Column('scope_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('budget', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('limitations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('ingest_state', sa.String(length=30), nullable=False),
    sa.Column('coverage_complete', sa.Boolean(), nullable=False),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('requested_by', sa.Uuid(), nullable=True),
    sa.Column('requested_by_label', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('snapshot_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status in ('queued','running','cancel_requested','completed','failed','canceled','interrupted')", name='ck_run_status'),
    sa.ForeignKeyConstraint(['baseline_run_id'], ['runs.id'], ),
    sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
    sa.ForeignKeyConstraint(['config_revision_id'], ['target_configs.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_runs_project_created', 'runs', ['project_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_runs_project_id'), 'runs', ['project_id'], unique=False)
    op.create_table('activities',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_activities_run', 'activities', ['run_id', 'at'], unique=False)
    op.create_table('run_stages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'code', name='uq_run_stage')
    )
    op.create_index(op.f('ix_run_stages_run_id'), 'run_stages', ['run_id'], unique=False)
    op.create_table('findings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('public_id', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('issue_class', sa.String(length=80), nullable=False),
    sa.Column('scope_summary', sa.String(length=400), nullable=False),
    sa.Column('actors_summary', sa.String(length=300), nullable=False),
    sa.Column('impact', sa.Text(), nullable=False),
    sa.Column('expected_behavior', sa.Text(), nullable=False),
    sa.Column('observed_behavior', sa.Text(), nullable=False),
    sa.Column('remediation', sa.Text(), nullable=False),
    sa.Column('prerequisites', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('reproduction_steps', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('root_cause_hypothesis', sa.Text(), nullable=True),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('evidence_status', sa.String(length=30), nullable=False),
    sa.Column('retest_method', sa.String(length=30), nullable=False),
    sa.Column('disposition', sa.String(length=20), nullable=False),
    sa.Column('disposition_reason', sa.Text(), nullable=False),
    sa.Column('first_run_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['first_run_id'], ['runs.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'public_id', name='uq_finding_public_id')
    )
    op.create_index('ix_findings_project_fingerprint', 'findings', ['project_id', 'fingerprint'], unique=False)
    op.create_index(op.f('ix_findings_project_id'), 'findings', ['project_id'], unique=False)
    op.create_table('surfaces',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('route', sa.String(length=300), nullable=False),
    sa.Column('methods', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('tested', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'route', name='uq_surface_route')
    )
    op.create_table('export_snapshots',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('format', sa.String(length=10), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('scope_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('schema_version', sa.String(length=20), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=True),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exports_run', 'export_snapshots', ['run_id', 'created_at'], unique=False)
    op.create_table('recipes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('finding_id')
    )
    op.create_index(op.f('ix_recipes_project_id'), 'recipes', ['project_id'], unique=False)
    op.create_table('run_checks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=True),
    sa.Column('check_key', sa.String(length=160), nullable=False),
    sa.Column('stage', sa.String(length=30), nullable=False),
    sa.Column('scenario_code', sa.String(length=80), nullable=False),
    sa.Column('scenario_title', sa.String(length=200), nullable=False),
    sa.Column('surface', sa.String(length=300), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('actor_label', sa.String(length=120), nullable=False),
    sa.Column('approach', sa.String(length=400), nullable=False),
    sa.Column('coverage_source', sa.String(length=40), nullable=False),
    sa.Column('result', sa.String(length=30), nullable=False),
    sa.Column('result_detail', sa.Text(), nullable=False),
    sa.Column('owasp_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'check_key', name='uq_run_check_key')
    )
    op.create_index('ix_run_checks_run', 'run_checks', ['run_id'], unique=False)
    op.create_table('ready_markers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('build_id', sa.Uuid(), nullable=False),
    sa.Column('marked_by', sa.Uuid(), nullable=True),
    sa.Column('marked_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ),
    sa.ForeignKeyConstraint(['marked_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('finding_id', 'build_id', name='uq_ready_marker')
    )
    op.create_table('recipe_revisions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('path_template', sa.String(length=300), nullable=False),
    sa.Column('fixture_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('identity_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('preconditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('expected_unauthorized', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('expected_authorized', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('assertion', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('approved_by', sa.Uuid(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('recipe_id', 'revision', name='uq_recipe_rev')
    )
    op.create_index(op.f('ix_recipe_revisions_recipe_id'), 'recipe_revisions', ['recipe_id'], unique=False)
    op.create_table('retest_attempts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('build_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('recipe_revision_id', sa.Uuid(), nullable=True),
    sa.Column('recipe_revision_label', sa.String(length=40), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('outcome', sa.String(length=30), nullable=True),
    sa.Column('reason_code', sa.String(length=60), nullable=True),
    sa.Column('reason_text', sa.Text(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('requested_by', sa.Uuid(), nullable=True),
    sa.Column('requested_by_label', sa.String(length=120), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('build_identity_expected', sa.String(length=160), nullable=False),
    sa.Column('build_identity_observed', sa.String(length=160), nullable=False),
    sa.Column('prerequisites', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('positive_control', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('assertion_result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_revision_id'], ['recipe_revisions.id'], ),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_attempts_finding_build', 'retest_attempts', ['finding_id', 'build_id'], unique=False)
    op.create_table('evidence',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=True),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('attempt_id', sa.Uuid(), nullable=True),
    sa.Column('build_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('attribution', sa.String(length=30), nullable=False),
    sa.Column('summary', sa.String(length=400), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('highlight', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=True),
    sa.Column('actor_label', sa.String(length=120), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('endpoint', sa.String(length=400), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], ),
    sa.ForeignKeyConstraint(['attempt_id'], ['retest_attempts.id'], ),
    sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_evidence_finding', 'evidence', ['finding_id', 'created_at'], unique=False)
    op.create_table('manual_reviews',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('attempt_id', sa.Uuid(), nullable=False),
    sa.Column('reviewer_id', sa.Uuid(), nullable=False),
    sa.Column('reviewer_label', sa.String(length=120), nullable=False),
    sa.Column('decision', sa.String(length=30), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['retest_attempts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_reviews_attempt_id'), 'manual_reviews', ['attempt_id'], unique=False)
    op.create_table('observations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('build_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('attempt_id', sa.Uuid(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('outcome', sa.String(length=30), nullable=False),
    sa.Column('accepted', sa.Boolean(), nullable=False),
    sa.Column('recipe_revision_id', sa.Uuid(), nullable=True),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reason_code', sa.String(length=60), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['retest_attempts.id'], ),
    sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_revision_id'], ['recipe_revisions.id'], ),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_observations_finding_build', 'observations', ['finding_id', 'build_id'], unique=False)
    # ### end Alembic commands ###

    # Cyclic foreign keys are added after both tables exist.
    op.create_foreign_key('fk_runs_cycle_jobs', 'runs', 'jobs', ['job_id'], ['id'])
    op.create_foreign_key('fk_jobs_cycle_runs', 'jobs', 'runs', ['run_id'], ['id'])

def downgrade() -> None:
    # Drop in reverse dependency order; indexes go with their tables.
    op.drop_table('observations')
    op.drop_table('manual_reviews')
    op.drop_table('evidence')
    op.drop_table('retest_attempts')
    op.drop_table('recipe_revisions')
    op.drop_table('ready_markers')
    op.drop_table('run_checks')
    op.drop_table('recipes')
    op.drop_table('export_snapshots')
    op.drop_table('surfaces')
    op.drop_table('findings')
    op.drop_table('run_stages')
    op.drop_table('activities')
    op.drop_table('runs')
    op.drop_table('jobs')
    op.drop_table('builds')
    op.drop_table('test_accounts')
    op.drop_table('target_configs')
    op.drop_table('project_members')
    op.drop_table('openapi_documents')
    op.drop_table('audit_events')
    op.drop_table('artifacts')
    op.drop_table('user_sessions')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('profiles')
    op.drop_table('login_attempts')
