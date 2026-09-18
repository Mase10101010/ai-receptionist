from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field


class TemporalSeatReleaseProjection(BaseModel):
    """
    Release truth for one currently occupied table.

    This object does not claim that the table is already free.
    It describes when Alias currently expects that capacity
    to become available.
    """

    table_id: UUID

    seat_capacity: int = Field(
        ge=1,
    )

    expected_release_at: datetime

    release_window_available: bool = False
    release_window_start_at: datetime | None = None
    release_window_end_at: datetime | None = None


class TemporalSeatReleaseHorizon(BaseModel):
    horizon_minutes: int

    expected_released_tables: int
    expected_released_seats: int

    conservative_released_tables: int
    conservative_released_seats: int


class TemporalSeatReleaseForecast(BaseModel):
    evaluated_at: datetime

    horizons: list[
        TemporalSeatReleaseHorizon
    ]


class TemporalSeatReleaseForecastService:
    """
    Aggregates expected table releases into future seat capacity.

    Expected capacity:
        expected_release_at is after evaluated_at
        and within the requested horizon.

    Conservative capacity:
        a reliable release window exists
        and its late bound is after evaluated_at
        and within the requested horizon.

    A currently seated table whose expected release is already
    in the past is NOT treated as released capacity.

    No DB.
    No probability.
    No demand model.
    No optimizer.
    No Brain.
    No Autopilot.
    """

    DEFAULT_HORIZONS = (
        30,
        60,
        90,
    )

    @classmethod
    def calculate(
        cls,
        *,
        projections: list[
            TemporalSeatReleaseProjection
        ],
        evaluated_at: datetime,
        horizons: tuple[int, ...] | None = None,
    ) -> TemporalSeatReleaseForecast:
        normalized_horizons = cls._normalize_horizons(
            horizons
            if horizons is not None
            else cls.DEFAULT_HORIZONS
        )

        cls._validate_unique_tables(
            projections
        )

        horizon_results: list[
            TemporalSeatReleaseHorizon
        ] = []

        for horizon_minutes in normalized_horizons:
            cutoff = (
                evaluated_at
                + timedelta(
                    minutes=horizon_minutes
                )
            )

            expected_tables = 0
            expected_seats = 0

            conservative_tables = 0
            conservative_seats = 0

            for projection in projections:
                if (
                    projection.expected_release_at
                    > evaluated_at
                    and projection.expected_release_at
                    <= cutoff
                ):
                    expected_tables += 1
                    expected_seats += (
                        projection.seat_capacity
                    )

                if not (
                    projection.release_window_available
                ):
                    continue

                late_bound = (
                    projection.release_window_end_at
                )

                if late_bound is None:
                    continue

                if (
                    late_bound > evaluated_at
                    and late_bound <= cutoff
                ):
                    conservative_tables += 1
                    conservative_seats += (
                        projection.seat_capacity
                    )

            horizon_results.append(
                TemporalSeatReleaseHorizon(
                    horizon_minutes=(
                        horizon_minutes
                    ),
                    expected_released_tables=(
                        expected_tables
                    ),
                    expected_released_seats=(
                        expected_seats
                    ),
                    conservative_released_tables=(
                        conservative_tables
                    ),
                    conservative_released_seats=(
                        conservative_seats
                    ),
                )
            )

        return TemporalSeatReleaseForecast(
            evaluated_at=evaluated_at,
            horizons=horizon_results,
        )

    @staticmethod
    def _normalize_horizons(
        horizons: tuple[int, ...],
    ) -> tuple[int, ...]:
        if not horizons:
            raise ValueError(
                "At least one forecast horizon is required."
            )

        if any(
            horizon <= 0
            for horizon in horizons
        ):
            raise ValueError(
                "Forecast horizons must be positive."
            )

        return tuple(
            sorted(
                set(horizons)
            )
        )

    @staticmethod
    def _validate_unique_tables(
        projections: list[
            TemporalSeatReleaseProjection
        ],
    ) -> None:
        table_ids = [
            projection.table_id
            for projection in projections
        ]

        if (
            len(table_ids)
            != len(set(table_ids))
        ):
            raise ValueError(
                "Seat release forecast cannot contain "
                "duplicate tables."
            )