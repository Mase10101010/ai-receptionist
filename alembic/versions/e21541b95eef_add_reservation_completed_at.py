"""add reservation completed at

Revision ID: e21541b95eef
Revises: 0684ff085165
Create Date: 2026-09-03 17:23:00.067878
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e21541b95eef'
down_revision: Union[str, None] = '0684ff085165'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "reservations",
        "completed_at",
    )
