"""add move complexity sample counts

Revision ID: abd82c00031f
Revises: 21338362ec8f
Create Date: 2026-08-29 12:06:21.756917
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "abd82c00031f"
down_revision: Union[str, None] = (
    "21338362ec8f"
)
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.add_column(
        "restaurant_learning_profiles",
        sa.Column(
            "accepted_move_complexity_samples",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "restaurant_learning_profiles",
        sa.Column(
            "dismissed_move_complexity_samples",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Backfill the number of historical manager
    # decisions that actually contain the
    # move_complexity_score signal.
    op.execute(
        sa.text(
            """
            UPDATE restaurant_learning_profiles AS p
            SET
                accepted_move_complexity_samples =
                    aggregated.accepted_samples,
                dismissed_move_complexity_samples =
                    aggregated.dismissed_samples
            FROM (
                SELECT
                    restaurant_id,

                    COUNT(*) FILTER (
                        WHERE
                            event_type =
                            'ai_suggestion_accepted'
                            AND payload
                                ? 'move_complexity_score'
                            AND payload
                                ->> 'move_complexity_score'
                                IS NOT NULL
                    ) AS accepted_samples,

                    COUNT(*) FILTER (
                        WHERE
                            event_type =
                            'ai_suggestion_dismissed'
                            AND payload
                                ? 'move_complexity_score'
                            AND payload
                                ->> 'move_complexity_score'
                                IS NOT NULL
                    ) AS dismissed_samples

                FROM intelligence_events

                GROUP BY restaurant_id
            ) AS aggregated

            WHERE
                p.restaurant_id =
                aggregated.restaurant_id
            """
        )
    )

    # Defaults were only needed to safely add the
    # NOT NULL columns to existing rows.
    op.alter_column(
        "restaurant_learning_profiles",
        "accepted_move_complexity_samples",
        server_default=None,
    )

    op.alter_column(
        "restaurant_learning_profiles",
        "dismissed_move_complexity_samples",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "restaurant_learning_profiles",
        "dismissed_move_complexity_samples",
    )

    op.drop_column(
        "restaurant_learning_profiles",
        "accepted_move_complexity_samples",
    )