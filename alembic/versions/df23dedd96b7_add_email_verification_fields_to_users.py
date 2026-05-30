"""add email verification fields to users

Revision ID: df23dedd96b7
Revises: fd641ca4b65d
Create Date: 2026-05-30 09:04:44.557758
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df23dedd96b7'
down_revision: Union[str, None] = 'fd641ca4b65d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "users",
        "is_active",
        server_default=sa.false(),
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "is_active",
        server_default=sa.true(),
    )

    op.drop_column("users", "is_email_verified")