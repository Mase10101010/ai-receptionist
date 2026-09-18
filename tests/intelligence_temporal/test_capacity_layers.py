from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.intelligence_temporal.capacity_layers import (
    TemporalCapacityLayersService,
    TemporalDirectCapacitySignal,
)
from app.intelligence_temporal.seat_release import (
    TemporalSeatReleaseForecast,
    TemporalSeatReleaseHorizon,
)


NOW = datetime(
    2026,
    9,
    6,
    20,
    0,
    tzinfo=timezone.utc,
)


def _forecast() -> TemporalSeatReleaseForecast:
    return TemporalSeatReleaseForecast(
        evaluated_at=NOW,
        horizons=[
            TemporalSeatReleaseHorizon(
                horizon_minutes=30,
                expected_released_tables=2,
                expected_released_seats=6,
                conservative_released_tables=1,
                conservative_released_seats=2,
            ),
            TemporalSeatReleaseHorizon(
                horizon_minutes=60,
                expected_released_tables=3,
                expected_released_seats=10,
                conservative_released_tables=2,
                conservative_released_seats=6,
            ),
            TemporalSeatReleaseHorizon(
                horizon_minutes=90,
                expected_released_tables=4,
                expected_released_seats=16,
                conservative_released_tables=4,
                conservative_released_seats=16,
            ),
        ],
    )


def test_preserves_direct_and_temporal_capacity_separately():
    result = TemporalCapacityLayersService.calculate(
        direct=TemporalDirectCapacitySignal(
            directly_available=True,
            assignment_capacity=4,
        ),
        release_forecast=_forecast(),
    )

    layer = result.layers[0]

    assert layer.horizon_minutes == 30

    assert layer.directly_available_now is True
    assert layer.direct_assignment_capacity == 4

    assert layer.expected_released_tables == 2
    assert layer.expected_released_seats == 6

    assert layer.conservative_released_tables == 1
    assert layer.conservative_released_seats == 2


def test_direct_unavailable_can_still_have_future_release():
    result = TemporalCapacityLayersService.calculate(
        direct=TemporalDirectCapacitySignal(
            directly_available=False,
            assignment_capacity=None,
        ),
        release_forecast=_forecast(),
    )

    layer = result.layers[0]

    assert layer.directly_available_now is False
    assert layer.direct_assignment_capacity is None

    assert layer.expected_released_seats == 6
    assert layer.conservative_released_seats == 2


def test_direct_availability_is_preserved_across_horizons():
    result = TemporalCapacityLayersService.calculate(
        direct=TemporalDirectCapacitySignal(
            directly_available=True,
            assignment_capacity=6,
        ),
        release_forecast=_forecast(),
    )

    assert len(result.layers) == 3

    assert all(
        layer.directly_available_now
        for layer in result.layers
    )

    assert all(
        layer.direct_assignment_capacity == 6
        for layer in result.layers
    )


def test_temporal_values_are_not_added_to_direct_assignment():
    result = TemporalCapacityLayersService.calculate(
        direct=TemporalDirectCapacitySignal(
            directly_available=True,
            assignment_capacity=4,
        ),
        release_forecast=_forecast(),
    )

    h30 = result.layers[0]

    # Important semantic invariant:
    # 4-seat direct assignment + 6 future released seats
    # is NOT exposed as "10 available seats".
    assert h30.direct_assignment_capacity == 4
    assert h30.expected_released_seats == 6

    assert not hasattr(
        h30,
        "total_available_seats",
    )


def test_available_direct_signal_requires_assignment_capacity():
    with pytest.raises(
        ValueError,
        match="requires an assignment capacity",
    ):
        TemporalCapacityLayersService.calculate(
            direct=TemporalDirectCapacitySignal(
                directly_available=True,
                assignment_capacity=None,
            ),
            release_forecast=_forecast(),
        )


def test_unavailable_direct_signal_rejects_assignment_capacity():
    with pytest.raises(
        ValueError,
        match="cannot expose",
    ):
        TemporalCapacityLayersService.calculate(
            direct=TemporalDirectCapacitySignal(
                directly_available=False,
                assignment_capacity=4,
            ),
            release_forecast=_forecast(),
        )


def test_direct_assignment_capacity_must_be_positive():
    with pytest.raises(
        ValueError,
        match="must be positive",
    ):
        TemporalCapacityLayersService.calculate(
            direct=TemporalDirectCapacitySignal(
                directly_available=True,
                assignment_capacity=0,
            ),
            release_forecast=_forecast(),
        )


def test_evaluated_at_is_preserved():
    result = TemporalCapacityLayersService.calculate(
        direct=TemporalDirectCapacitySignal(
            directly_available=False,
        ),
        release_forecast=_forecast(),
    )

    assert result.evaluated_at == NOW