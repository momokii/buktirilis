"""correct backfilled evidence timestamps

Revision ID: fd9dae61da04
Revises: e2f921369308
Create Date: 2026-11-16 20:15:50.656278
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'fd9dae61da04'  # pragma: allowlist secret
down_revision = 'e2f921369308'  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing findings had no review timeline before the evidence_decisions table.
    # Stamping the current status at finding creation would make old snapshots claim a
    # decision that was never recorded; move the synthetic entry to migration time and
    # label it explicitly. Comparisons before that point fall back to current state.
    op.execute(
        """
        UPDATE evidence_decisions
        SET created_at = now(),
            reason = 'Backfilled current status at migration time; no historical review timeline'
        WHERE actor_label = 'migration'
        """
    )


def downgrade() -> None:
    # The original timestamp is not recoverable without the previous migration state.
    pass
