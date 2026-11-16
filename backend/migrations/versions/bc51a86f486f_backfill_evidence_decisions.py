"""backfill evidence decisions

Revision ID: bc51a86f486f
Revises: 6c715d92eb85
Create Date: 2026-11-16 08:23:15.519947
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'bc51a86f486f'
down_revision = '6c715d92eb85'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO evidence_decisions
            (id, project_id, finding_id, status, reason, actor_label, created_at)
        SELECT gen_random_uuid(), f.project_id, f.id, f.evidence_status,
               'Initial evidence assessment (backfilled)', 'migration', f.created_at
        FROM findings f
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence_decisions d WHERE d.finding_id = f.id
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM evidence_decisions WHERE actor_label = 'migration'")
