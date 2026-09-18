"""repair reservation seated at

Revision ID: 129de234d50e
Revises: d77748f5cf14
Create Date: 2026-09-03 17:41:53.976594

This migration is intentionally a no-op.

The seated_at column is already created by revision
0684ff085165. This revision is preserved to maintain
the existing Alembic revision chain without attempting
to create the column a second time.
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "129de234d50e"
down_revision: Union[str, None] = "d77748f5cf14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass