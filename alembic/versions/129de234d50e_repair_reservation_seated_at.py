"""repair reservation seated at

Revision ID: 129de234d50e
Revises: d77748f5cf14
Create Date: 2026-09-03 17:41:53.976594
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '129de234d50e'
down_revision: Union[str, None] = 'd77748f5cf14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column(
            "seated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("reservations", "seated_at")