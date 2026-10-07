"""add live seated modification suggestion type

Revision ID: 89dc87af6004
Revises: 9831eded325d
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "89dc87af6004"
down_revision: Union[str, None] = "9831eded325d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TYPE ai_suggestion_type
        ADD VALUE IF NOT EXISTS 'live_seated_modification'
        """
    )


def downgrade() -> None:
    # PostgreSQL enum values are intentionally append-only here.
    #
    # Removing an enum value safely would require rebuilding the enum
    # type and every dependent column, which is disproportionate and
    # risky for this migration.
    pass
