"""add restaurant availability fields

Revision ID: 2af59a3d73c5
Revises: d98f4016b3ca
Create Date: 2026-05-19 11:24:26.588395
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2af59a3d73c5'
down_revision: Union[str, None] = 'd98f4016b3ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'restaurants',
        sa.Column('table_setup', sa.JSON(), nullable=True),
    )

    op.add_column(
        'restaurants',
        sa.Column('weekly_schedule', sa.JSON(), nullable=True),
    )

    op.add_column(
        'restaurants',
        sa.Column('special_closures', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('restaurants', 'special_closures')
    op.drop_column('restaurants', 'weekly_schedule')
    op.drop_column('restaurants', 'table_setup')
