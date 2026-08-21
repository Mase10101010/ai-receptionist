"""add dismissed learning metrics

Revision ID: 8c7e2d91f4a6
Revises: 1a4d3b38e802
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c7e2d91f4a6"
down_revision: Union[str, None] = (
    "1a4d3b38e802"
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
            "dismissed_moves_average",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "restaurant_learning_profiles",
        sa.Column(
            "dismissed_seat_waste_average",
            sa.Float(),
            nullable=True,
        ),
    )

    # Backfill the new metrics from the existing
    # intelligence event store.
    #
    # We intentionally derive the values from the
    # original events instead of inventing defaults,
    # so historical manager decisions remain valid
    # learning evidence.
    op.execute(
        sa.text(
            """
            UPDATE restaurant_learning_profiles AS p
            SET
                dismissed_moves_average =
                    aggregated.average_moves,
                dismissed_seat_waste_average =
                    aggregated.average_seat_waste
            FROM (
                SELECT
                    restaurant_id,

                    AVG(
                        CAST(
                            payload
                            ->> 'moved_reservations_count'
                            AS DOUBLE PRECISION
                        )
                    ) AS average_moves,

                    AVG(
                        CAST(
                            payload
                            ->> 'total_seat_waste'
                            AS DOUBLE PRECISION
                        )
                    ) AS average_seat_waste

                FROM intelligence_events

                WHERE
                    event_type =
                    'ai_suggestion_dismissed'

                GROUP BY restaurant_id
            ) AS aggregated

            WHERE
                p.restaurant_id =
                aggregated.restaurant_id
            """
        )
    )


def downgrade() -> None:
    op.drop_column(
        "restaurant_learning_profiles",
        "dismissed_seat_waste_average",
    )

    op.drop_column(
        "restaurant_learning_profiles",
        "dismissed_moves_average",
    )