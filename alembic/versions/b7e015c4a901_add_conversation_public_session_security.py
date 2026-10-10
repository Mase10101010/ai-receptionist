"""Add restaurant ownership and public session capability to conversations.

Revision ID: b7e015c4a901
Revises: a194eccd7d56
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e015c4a901"
down_revision = "a194eccd7d56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("restaurant_id", sa.UUID(), nullable=True),
    )

    op.add_column(
        "conversations",
        sa.Column(
            "public_access_token_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )

    # Attribute historical conversations only when all associated
    # reservations have a known, identical restaurant owner.
    # Unattributable or ambiguous conversations remain NULL.
    op.execute(
        """
        UPDATE conversations AS c
        SET restaurant_id = ownership.restaurant_id
        FROM (
            SELECT
                session_id,
                MIN(restaurant_id::text)::uuid AS restaurant_id
            FROM reservations
            WHERE session_id IS NOT NULL
            GROUP BY session_id
            HAVING COUNT(*) = COUNT(restaurant_id)
               AND COUNT(DISTINCT restaurant_id) = 1
        ) AS ownership
        WHERE c.session_id = ownership.session_id
        """
    )

    op.create_index(
        "ix_conversations_restaurant_id",
        "conversations",
        ["restaurant_id"],
    )

    op.create_foreign_key(
        "fk_conversations_restaurant_id",
        "conversations",
        "restaurants",
        ["restaurant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_restaurant_id",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_conversations_restaurant_id",
        table_name="conversations",
    )
    op.drop_column("conversations", "public_access_token_hash")
    op.drop_column("conversations", "restaurant_id")
