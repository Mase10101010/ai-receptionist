"""add restaurant onboarding status

Revision ID: bdc0c67f35ec
Revises: 56e14548ca0a
Create Date: 2026-08-03 21:48:34.894495
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdc0c67f35ec'
down_revision: Union[str, None] = '56e14548ca0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "restaurants",
        "onboarding_completed",
    )
