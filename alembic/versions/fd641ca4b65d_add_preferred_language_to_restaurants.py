"""add preferred language to restaurants

Revision ID: fd641ca4b65d
Revises: 2af59a3d73c5
Create Date: 2026-05-29 11:49:55.053086
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd641ca4b65d'
down_revision: Union[str, None] = '2af59a3d73c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column(
            "preferred_language",
            sa.String(length=10),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurants", "preferred_language")
