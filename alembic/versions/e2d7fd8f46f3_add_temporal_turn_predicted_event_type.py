"""add temporal turn predicted event type

Revision ID: e2d7fd8f46f3
Revises: 129de234d50e
Create Date: 2026-09-04 09:56:26.977779
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e2d7fd8f46f3"
down_revision: Union[str, None] = "129de234d50e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TYPE intelligence_event_type
        ADD VALUE IF NOT EXISTS 'temporal_turn_predicted'
        """
    )


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed in-place
    # without rebuilding the enum type and every dependent column.
    #
    # This migration is intentionally append-only.
    pass