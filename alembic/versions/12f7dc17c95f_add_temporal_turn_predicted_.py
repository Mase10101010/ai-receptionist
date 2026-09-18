"""add temporal turn predicted intelligence event type

Revision ID: 12f7dc17c95f
Revises: e2d7fd8f46f3
Create Date: 2026-09-04 10:19:27.202473
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "12f7dc17c95f"
down_revision: Union[str, None] = "e2d7fd8f46f3"
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
    # PostgreSQL enum values are intentionally append-only here.
    #
    # Removing an enum value safely would require rebuilding the enum
    # type and every dependent column, which is disproportionate and
    # risky for this migration.
    pass