"""add reservation access tokens

Revision ID: a194eccd7d56
Revises: 89dc87af6004
Create Date: 2026-10-09 02:26:46.594234
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a194eccd7d56'
down_revision: Union[str, None] = '89dc87af6004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_reservations_id_restaurant_id",
        "reservations",
        ["id", "restaurant_id"],
    )

    op.create_table(
        "reservation_access_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("restaurant_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id", "restaurant_id"],
            ["reservations.id", "reservations.restaurant_id"],
            name="fk_reservation_access_tokens_reservation_restaurant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )

    op.create_index(
        "ix_reservation_access_tokens_reservation_id",
        "reservation_access_tokens",
        ["reservation_id"],
    )

    op.create_index(
        "ix_reservation_access_tokens_restaurant_id",
        "reservation_access_tokens",
        ["restaurant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reservation_access_tokens_restaurant_id",
        table_name="reservation_access_tokens",
    )
    op.drop_index(
        "ix_reservation_access_tokens_reservation_id",
        table_name="reservation_access_tokens",
    )
    op.drop_table("reservation_access_tokens")
    op.drop_constraint(
        "uq_reservations_id_restaurant_id",
        "reservations",
        type_="unique",
    )
