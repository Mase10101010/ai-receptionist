from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.intelligence_temporal.capacity_layers import (
    TemporalCapacityLayer,
    TemporalCapacityLayers,
)
from app.intelligence_temporal.capacity_pressure import (
    TemporalCapacityPressureState,
)
from app.intelligence_temporal.future_capacity_snapshot import (
    TemporalFutureCapacitySnapshotService,
)
from app.intelligence_temporal.peak_periods import (
    TemporalPeakState,
)
from app.intelligence_temporal.saturation import (
    TemporalSaturationSlot,
    TemporalSaturationState,
)


NOW = datetime(
    2026,
    9,
    6,
    20,
    0,
    tzinfo=timezone.utc,
)


def _capacity(
    *,
    direct: bool = False,
    conservative_30: int = 0,
    expected_30: int = 0,
    conservative_60: int = 4,
    expected_60: int = 4,
) -> TemporalCapacityLayers:
    return TemporalCapacityLayers(
        evaluated_at=NOW,
        layers=[
            TemporalCapacityLayer(
                horizon_minutes=30,
                directly_available_now=direct,
                direct_assignment_capacity=(
                    4
                    if direct
                    else None
                ),
                expected_released_tables=(
                    1
                    if expected_30 > 0
                    else 0
                ),
                expected_released_seats=(
                    expected_30
                ),
                conservative_released_tables=(
                    1
                    if conservative_30 > 0
                    else 0
                ),
                conservative_released_seats=(
                    conservative_30
                ),
            ),
            TemporalCapacityLayer(
                horizon_minutes=60,
                directly_available_now=direct,
                direct_assignment_capacity=(
                    4
                    if direct
                    else None
                ),
                expected_released_tables=(
                    1
                    if expected_60 > 0
                    else 0
                ),
                expected_released_seats=(
                    expected_60
                ),
                conservative_released_tables=(
                    1
                    if conservative_60 > 0
                    else 0
                ),
                conservative_released_seats=(
                    conservative_60
                ),
            ),
        ],
    )


def _slots(
    availability: list[bool],
    *,
    start: datetime = NOW,
) -> list[TemporalSaturationSlot]:
    return [
        TemporalSaturationSlot(
            slot_time=(
                start
                + timedelta(
                    minutes=index * 15
                )
            ),
            directly_available=available,
        )
        for index, available
        in enumerate(availability)
    ]


def test_builds_complete_future_capacity_snapshot():
    slots = _slots(
        [
            False,
            False,
            True,
            True,
        ]
    )

    result = (
        TemporalFutureCapacitySnapshotService
        .build(
            capacity=_capacity(
                expected_30=4,
                conservative_30=4,
            ),
            saturation_slots=slots,
            peak_periods=[
                slots,
            ],
        )
    )

    assert result.capacity.evaluated_at == NOW

    assert (
        result.pressure.state
        == (
            TemporalCapacityPressureState
            .RECOVERING_SOON
        )
    )

    assert (
        result.saturation.state
        == TemporalSaturationState.MODERATE
    )

    assert len(result.peak_profile.periods) == 1


def test_direct_capacity_produces_clear_pressure():
    result = (
        TemporalFutureCapacitySnapshotService
        .build(
            capacity=_capacity(
                direct=True,
            ),
            saturation_slots=_slots(
                [
                    True,
                    True,
                    True,
                ]
            ),
            peak_periods=[
                _slots(
                    [
                        True,
                        True,
                        True,
                    ]
                )
            ],
        )
    )

    assert (
        result.pressure.state
        == TemporalCapacityPressureState.CLEAR
    )


def test_saturation_is_calculated_from_supplied_slots():
    result = (
        TemporalFutureCapacitySnapshotService
        .build(
            capacity=_capacity(),
            saturation_slots=_slots(
                [
                    False,
                    False,
                    False,
                    True,
                    True,
                ]
            ),
            peak_periods=[],
        )
    )

    assert result.saturation.unavailable_ratio == 0.6

    assert (
        result.saturation.state
        == TemporalSaturationState.HIGH
    )


def test_peak_periods_are_classified_independently():
    off_peak = _slots(
        [
            True,
            True,
            True,
            True,
        ]
    )

    peak = _slots(
        [
            False,
            False,
            False,
            True,
        ],
        start=(
            NOW
            + timedelta(
                hours=1
            )
        ),
    )

    result = (
        TemporalFutureCapacitySnapshotService
        .build(
            capacity=_capacity(),
            saturation_slots=(
                off_peak
                + peak
            ),
            peak_periods=[
                off_peak,
                peak,
            ],
        )
    )

    assert [
        period.state
        for period in result.peak_profile.periods
    ] == [
        TemporalPeakState.OFF_PEAK,
        TemporalPeakState.PEAK,
    ]

def test_uncertain_release_truth_is_preserved():
    result = (
        TemporalFutureCapacitySnapshotService
        .build(
            capacity=_capacity(
                expected_30=4,
                conservative_30=0,
                expected_60=4,
                conservative_60=0,
            ),
            saturation_slots=_slots(
                [
                    False,
                    True,
                ]
            ),
            peak_periods=[],
        )
    )

    assert (
        result.pressure.state
        == (
            TemporalCapacityPressureState
            .UNCERTAIN_RECOVERY
        )
    )


def test_empty_saturation_profile_is_valid():
    result = (
        TemporalFutureCapacitySnapshotService
        .build(
            capacity=_capacity(),
            saturation_slots=[],
            peak_periods=[],
        )
    )

    assert result.saturation.total_slots == 0
    assert result.peak_profile.periods == []


def test_empty_capacity_layers_fail_closed():
    with pytest.raises(
        ValueError,
        match="at least one capacity layer",
    ):
        (
            TemporalFutureCapacitySnapshotService
            .build(
                capacity=TemporalCapacityLayers(
                    evaluated_at=NOW,
                    layers=[],
                ),
                saturation_slots=[],
                peak_periods=[],
            )
        )


def test_past_saturation_slot_fails_closed():
    with pytest.raises(
        ValueError,
        match="cannot precede evaluated_at",
    ):
        (
            TemporalFutureCapacitySnapshotService
            .build(
                capacity=_capacity(),
                saturation_slots=[
                    TemporalSaturationSlot(
                        slot_time=(
                            NOW
                            - timedelta(
                                minutes=15
                            )
                        ),
                        directly_available=True,
                    )
                ],
                peak_periods=[],
            )
        )