"""add_owner_id_to_restaurants

Revision ID: f465a1572227
Revises: e8c5237ef25b
Create Date: 2026-06-06 11:27:40.757437
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f465a1572227'
down_revision: Union[str, None] = 'e8c5237ef25b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    owner_id = "f73da397-3561-412a-a25b-9251a1abc631"

    op.add_column(
        "restaurants",
        sa.Column("owner_id", sa.UUID(), nullable=True),
    )

    op.execute(
        f"UPDATE restaurants SET owner_id = '{owner_id}' WHERE owner_id IS NULL"
    )

    op.alter_column(
        "restaurants",
        "owner_id",
        nullable=False,
    )

    op.create_index(
        op.f("ix_restaurants_owner_id"),
        "restaurants",
        ["owner_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_restaurants_owner_id_users",
        "restaurants",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_restaurants_owner_id_users",
        "restaurants",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_restaurants_owner_id"),
        table_name="restaurants",
    )
    op.drop_column("restaurants", "owner_id")