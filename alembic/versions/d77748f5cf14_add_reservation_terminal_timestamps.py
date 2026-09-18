"""add reservation terminal timestamps

Revision ID: d77748f5cf14
Revises: e21541b95eef
Create Date: 2026-09-03 17:33:55.829209
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd77748f5cf14'
down_revision: Union[str, None] = 'e21541b95eef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "no_show_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("reservations", "no_show_at")
    op.drop_column("reservations", "cancelled_at")
