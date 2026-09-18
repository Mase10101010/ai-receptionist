"""add restaurant autopilot enabled

Revision ID: f35bf244cef3
Revises: abd82c00031f
Create Date: 2026-09-03 09:38:26.336660
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f35bf244cef3'
down_revision: Union[str, None] = 'abd82c00031f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column(
            "autopilot_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "restaurants",
        "autopilot_enabled",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "restaurants",
        "autopilot_enabled",
    )
