from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.intelligence_temporal.capacity_layers import (
    TemporalCapacityLayer,
    TemporalCapacityLayers,
)
from app.intelligence_temporal.capacity_pressure import (
    TemporalCapacityPressureService,
    TemporalCapacityPressureState,
)


NOW = datetime(
    2026,
    9,
    6,
    20,
    0,
    tzinfo=timezone.utc,
)


def _layer(
    *,
    horizon: int,
    direct: bool = False,
    expected_seats: int = 0,
    conservative_seats: int = 0,
) -> TemporalCapacityLayer:
    return TemporalCapacityLayer(
        horizon_minutes=horizon,
        directly_available_now=direct,
        direct_assignment_capacity=(
            4
            if direct
            else None
        ),
        expected_released_tables=(
            1
            if expected_seats > 0
            else 0
        ),
        expected_released_seats=(
            expected_seats
        ),
        conservative_released_tables=(
            1
            if conservative_seats > 0
            else 0
        ),
        conservative_released_seats=(
            conservative_seats
        ),
    )


def _capacity(
    layers: list[
        TemporalCapacityLayer
    ],
) -> TemporalCapacityLayers:
    return TemporalCapacityLayers(
        evaluated_at=NOW,
        layers=layers,
    )


def test_direct_capacity_is_clear():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=30,
                        direct=True,
                    ),
                    _layer(
                        horizon=60,
                        direct=True,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == TemporalCapacityPressureState.CLEAR
    )

    assert (
        result.directly_available_now
        is True
    )


def test_conservative_release_within_30_is_recovering_soon():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=30,
                        expected_seats=4,
                        conservative_seats=4,
                    ),
                    _layer(
                        horizon=60,
                        expected_seats=8,
                        conservative_seats=8,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == (
            TemporalCapacityPressureState
            .RECOVERING_SOON
        )
    )

    assert (
        result
        .first_conservative_release_horizon_minutes
        == 30
    )

    assert (
        result
        .conservative_released_seats_at_first_horizon
        == 4
    )


def test_conservative_release_after_30_is_recovering_later():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=30,
                    ),
                    _layer(
                        horizon=60,
                        expected_seats=4,
                        conservative_seats=4,
                    ),
                    _layer(
                        horizon=90,
                        expected_seats=8,
                        conservative_seats=8,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == (
            TemporalCapacityPressureState
            .RECOVERING_LATER
        )
    )

    assert (
        result
        .first_conservative_release_horizon_minutes
        == 60
    )


def test_expected_only_release_is_uncertain_recovery():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=30,
                        expected_seats=4,
                    ),
                    _layer(
                        horizon=60,
                        expected_seats=8,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == (
            TemporalCapacityPressureState
            .UNCERTAIN_RECOVERY
        )
    )

    assert (
        result
        .first_expected_release_horizon_minutes
        == 30
    )

    assert (
        result
        .first_conservative_release_horizon_minutes
        is None
    )


def test_no_capacity_and_no_release_is_blocked():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=30,
                    ),
                    _layer(
                        horizon=60,
                    ),
                    _layer(
                        horizon=90,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == TemporalCapacityPressureState.BLOCKED
    )

    assert (
        result
        .first_expected_release_horizon_minutes
        is None
    )

    assert (
        result
        .first_conservative_release_horizon_minutes
        is None
    )


def test_direct_capacity_has_priority_over_future_pressure():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=30,
                        direct=True,
                        expected_seats=2,
                    ),
                    _layer(
                        horizon=60,
                        direct=True,
                        expected_seats=6,
                        conservative_seats=4,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == TemporalCapacityPressureState.CLEAR
    )


def test_first_release_horizon_uses_chronological_order():
    result = (
        TemporalCapacityPressureService
        .calculate(
            capacity=_capacity(
                [
                    _layer(
                        horizon=90,
                        expected_seats=8,
                        conservative_seats=8,
                    ),
                    _layer(
                        horizon=30,
                    ),
                    _layer(
                        horizon=60,
                        expected_seats=4,
                        conservative_seats=4,
                    ),
                ]
            )
        )
    )

    assert (
        result.state
        == (
            TemporalCapacityPressureState
            .RECOVERING_LATER
        )
    )

    assert (
        result
        .first_conservative_release_horizon_minutes
        == 60
    )


def test_empty_capacity_layers_fail_closed():
    with pytest.raises(
        ValueError,
        match="at least one capacity layer",
    ):
        (
            TemporalCapacityPressureService
            .calculate(
                capacity=TemporalCapacityLayers(
                    evaluated_at=NOW,
                    layers=[],
                )
            )
        )