"""add temporal turn outcome recorded event type

Revision ID: 14ac0a0dbd21
Revises: 12f7dc17c95f
Create Date: 2026-09-05 09:52:58.882045
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14ac0a0dbd21'
down_revision: Union[str, None] = '12f7dc17c95f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TYPE intelligence_event_type
        ADD VALUE IF NOT EXISTS
        'temporal_turn_outcome_recorded'
        """
    )


def downgrade() -> None:
    pass
