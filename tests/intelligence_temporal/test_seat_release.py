from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.intelligence_temporal.seat_release import (
    TemporalSeatReleaseForecastService,
    TemporalSeatReleaseProjection,
)


NOW = datetime(
    2026,
    9,
    6,
    20,
    0,
    tzinfo=timezone.utc,
)


def _projection(
    *,
    expected_minutes: int,
    seats: int = 4,
    window_end_minutes: int | None = None,
) -> TemporalSeatReleaseProjection:
    return TemporalSeatReleaseProjection(
        table_id=uuid4(),
        seat_capacity=seats,
        expected_release_at=(
            NOW
            + timedelta(
                minutes=expected_minutes
            )
        ),
        release_window_available=(
            window_end_minutes is not None
        ),
        release_window_start_at=(
            NOW
            + timedelta(
                minutes=max(
                    1,
                    expected_minutes - 10,
                )
            )
            if window_end_minutes is not None
            else None
        ),
        release_window_end_at=(
            NOW
            + timedelta(
                minutes=window_end_minutes
            )
            if window_end_minutes is not None
            else None
        ),
    )


def _horizon(
    forecast,
    minutes: int,
):
    return next(
        horizon
        for horizon in forecast.horizons
        if horizon.horizon_minutes == minutes
    )


def test_expected_release_enters_matching_horizon():
    forecast = (
        TemporalSeatReleaseForecastService
        .calculate(
            projections=[
                _projection(
                    expected_minutes=20,
                    seats=4,
                )
            ],
            evaluated_at=NOW,
        )
    )

    h30 = _horizon(
        forecast,
        30,
    )

    assert h30.expected_released_tables == 1
    assert h30.expected_released_seats == 4

    assert (
        h30.conservative_released_tables
        == 0
    )
    assert (
        h30.conservative_released_seats
        == 0
    )


def test_conservative_capacity_uses_late_window_bound():
    forecast = (
        TemporalSeatReleaseForecastService
        .calculate(
            projections=[
                _projection(
                    expected_minutes=20,
                    seats=4,
                    window_end_minutes=40,
                )
            ],
            evaluated_at=NOW,
        )
    )

    h30 = _horizon(
        forecast,
        30,
    )

    assert h30.expected_released_seats == 4

    assert (
        h30.conservative_released_seats
        == 0
    )

    h60 = _horizon(
        forecast,
        60,
    )

    assert h60.expected_released_seats == 4

    assert (
        h60.conservative_released_seats
        == 4
    )


def test_past_expected_release_is_not_future_capacity():
    projection = TemporalSeatReleaseProjection(
        table_id=uuid4(),
        seat_capacity=4,
        expected_release_at=(
            NOW
            - timedelta(
                minutes=10
            )
        ),
        release_window_available=True,
        release_window_start_at=(
            NOW
            - timedelta(
                minutes=20
            )
        ),
        release_window_end_at=(
            NOW
            - timedelta(
                minutes=5
            )
        ),
    )

    forecast = (
        TemporalSeatReleaseForecastService
        .calculate(
            projections=[projection],
            evaluated_at=NOW,
        )
    )

    for horizon in forecast.horizons:
        assert (
            horizon.expected_released_seats
            == 0
        )
        assert (
            horizon.conservative_released_seats
            == 0
        )


def test_missing_release_window_keeps_expected_only():
    forecast = (
        TemporalSeatReleaseForecastService
        .calculate(
            projections=[
                _projection(
                    expected_minutes=15,
                    seats=6,
                )
            ],
            evaluated_at=NOW,
        )
    )

    h30 = _horizon(
        forecast,
        30,
    )

    assert h30.expected_released_seats == 6

    assert (
        h30.conservative_released_seats
        == 0
    )


def test_multiple_tables_are_aggregated():
    forecast = (
        TemporalSeatReleaseForecastService
        .calculate(
            projections=[
                _projection(
                    expected_minutes=10,
                    seats=2,
                    window_end_minutes=15,
                ),
                _projection(
                    expected_minutes=25,
                    seats=4,
                    window_end_minutes=35,
                ),
                _projection(
                    expected_minutes=70,
                    seats=6,
                    window_end_minutes=80,
                ),
            ],
            evaluated_at=NOW,
        )
    )

    h30 = _horizon(
        forecast,
        30,
    )

    assert h30.expected_released_tables == 2
    assert h30.expected_released_seats == 6

    assert (
        h30.conservative_released_tables
        == 1
    )
    assert (
        h30.conservative_released_seats
        == 2
    )

    h60 = _horizon(
        forecast,
        60,
    )

    assert h60.expected_released_seats == 6
    assert h60.conservative_released_seats == 6

    h90 = _horizon(
        forecast,
        90,
    )

    assert h90.expected_released_seats == 12
    assert h90.conservative_released_seats == 12


def test_duplicate_table_fails_closed():
    table_id = uuid4()

    projections = [
        TemporalSeatReleaseProjection(
            table_id=table_id,
            seat_capacity=4,
            expected_release_at=(
                NOW
                + timedelta(
                    minutes=20
                )
            ),
        ),
        TemporalSeatReleaseProjection(
            table_id=table_id,
            seat_capacity=4,
            expected_release_at=(
                NOW
                + timedelta(
                    minutes=30
                )
            ),
        ),
    ]

    with pytest.raises(
        ValueError,
        match="duplicate tables",
    ):
        (
            TemporalSeatReleaseForecastService
            .calculate(
                projections=projections,
                evaluated_at=NOW,
            )
        )


def test_custom_horizons_are_normalized():
    forecast = (
        TemporalSeatReleaseForecastService
        .calculate(
            projections=[],
            evaluated_at=NOW,
            horizons=(
                90,
                30,
                60,
                30,
            ),
        )
    )

    assert [
        horizon.horizon_minutes
        for horizon in forecast.horizons
    ] == [
        30,
        60,
        90,
    ]


def test_invalid_horizon_fails_closed():
    with pytest.raises(
        ValueError,
        match="positive",
    ):
        (
            TemporalSeatReleaseForecastService
            .calculate(
                projections=[],
                evaluated_at=NOW,
                horizons=(
                    30,
                    0,
                    60,
                ),
            )
        )