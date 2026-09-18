"""repair temporal intelligence event enum

Revision ID: 8c2378621a3d
Revises: 14ac0a0dbd21
"""

from alembic import op


revision = "8c2378621a3d"
down_revision = "14ac0a0dbd21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TYPE intelligence_event_type
        ADD VALUE IF NOT EXISTS 'temporal_turn_predicted'
        """
    )

    op.execute(
        """
        ALTER TYPE intelligence_event_type
        ADD VALUE IF NOT EXISTS 'temporal_turn_outcome_recorded'
        """
    )


def downgrade() -> None:
    # PostgreSQL enum values are intentionally append-only.
    pass