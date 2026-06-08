"""add_stripe_subscription_fields

Revision ID: e8c5237ef25b
Revises: 9fe8b3b43c25
Create Date: 2026-06-06 06:28:57.685610
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8c5237ef25b'
down_revision: Union[str, None] = '9fe8b3b43c25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "restaurants",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "restaurants",
        sa.Column("trial_start_date", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "restaurants",
        sa.Column("trial_end_date", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "restaurants",
        sa.Column("subscription_start_date", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "restaurants",
        sa.Column("subscription_end_date", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "restaurants",
        sa.Column(
            "has_used_trial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.execute(
        "UPDATE restaurants SET subscription_status = 'lifetime'"
    )


def downgrade() -> None:
    op.drop_column("restaurants", "has_used_trial")
    op.drop_column("restaurants", "subscription_end_date")
    op.drop_column("restaurants", "subscription_start_date")
    op.drop_column("restaurants", "trial_end_date")
    op.drop_column("restaurants", "trial_start_date")
    op.drop_column("restaurants", "stripe_subscription_id")
    op.drop_column("restaurants", "stripe_customer_id")