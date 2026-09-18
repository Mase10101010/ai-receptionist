from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import pytest

from app.intelligence_temporal.capacity_pressure import (
    TemporalCapacityPressureState,
)
from app.intelligence_temporal.future_capacity_coordinator import (
    TemporalFutureCapacityCoordinator,
)
from app.intelligence_temporal.live_intelligence import (
    TemporalLiveIntelligence,
)
from app.intelligence_temporal.live_signal import (
    TemporalLiveSignal,
    TemporalLiveSignalState,
)
from app.intelligence_temporal.live_turn import (
    LiveTurnPrediction,
    LiveTurnState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.release_window import (
    TemporalReleaseWindow,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)
from app.intelligence_temporal.saturation import (
    TemporalSaturationState,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)


def _profile(
    availability: list[bool],
    *,
    assignment_capacity: int = 4,
) -> FutureCapacityResponse:
    slots = []

    for index, available in enumerate(
        availability
    ):
        start = (
            NOW
            + timedelta(
                minutes=index * 30
            )
        )

        slots.append(
            FutureCapacitySlot(
                start_at=start,
                end_at=(
                    start
                    + timedelta(
                        minutes=90
                    )
                ),
                directly_available=available,
                assignment_capacity=(
                    assignment_capacity
                    if available
                    else None
                ),
            )
        )

    available_count = sum(
        1
        for available in availability
        if available
    )

    first_available = next(
        (
            slot.start_at
            for slot in slots
            if slot.directly_available
        ),
        None,
    )

    longest_run = 0
    current_run = 0

    for available in availability:
        if available:
            current_run += 1
            longest_run = max(
                longest_run,
                current_run,
            )
        else:
            current_run = 0

    return FutureCapacityResponse(
        restaurant_id=uuid4(),
        start_at=NOW,
        party_size=2,
        duration_minutes=90,
        horizon_minutes=(
            (len(availability) - 1) * 30
            if availability
            else 0
        ),
        slot_minutes=30,
        slots=slots,
        summary=FutureCapacitySummary(
            total_slots=len(slots),
            directly_available_slots=(
                available_count
            ),
            unavailable_slots=(
                len(slots)
                - available_count
            ),
            availability_ratio=(
                available_count / len(slots)
                if slots
                else 0.0
            ),
            first_directly_available_at=(
                first_available
            ),
            longest_directly_available_run=(
                longest_run
            ),
        ),
    )


def _live(
    *,
    expected_release_minutes: int,
    reliable_window: bool = False,
    window_end_minutes: int | None = None,
) -> TemporalLiveIntelligence:
    expected_release_at = (
        NOW
        + timedelta(
            minutes=(
                expected_release_minutes
            )
        )
    )

    window_start = None
    window_end = None

    if reliable_window:
        window_start = (
            expected_release_at
            - timedelta(minutes=5)
        )

        window_end = (
            NOW
            + timedelta(
                minutes=(
                    window_end_minutes
                    if window_end_minutes
                    is not None
                    else (
                        expected_release_minutes
                        + 5
                    )
                )
            )
        )

    live_turn = LiveTurnPrediction(
        seated_at=(
            NOW
            - timedelta(minutes=30)
        ),
        evaluated_at=NOW,
        expected_duration_minutes=60,
        expected_release_at=(
            expected_release_at
        ),
        elapsed_minutes=30,
        remaining_minutes=max(
            0,
            expected_release_minutes,
        ),
        overrun_minutes=0,
        state=LiveTurnState.IN_PROGRESS,
        source=ExpectedTurnSource.PLANNED_FALLBACK,
        source_sample_count=None,
        confidence=ExpectedTurnConfidence.LOW,
        used_learned_pattern=False,
    )

    release_window = TemporalReleaseWindow(
        expected_release_at=(
            expected_release_at
        ),
        window_start_at=window_start,
        window_end_at=window_end,
        available=reliable_window,
        sample_count=(
            20
            if reliable_window
            else 0
        ),
        calibration_state=(
            "well_calibrated"
            if reliable_window
            else "insufficient_data"
        ),
    )

    signal = TemporalLiveSignal(
        state=TemporalLiveSignalState.IN_SERVICE,
        expected_release_at=(
            expected_release_at
        ),
        remaining_minutes=max(
            0,
            expected_release_minutes,
        ),
        overrun_minutes=0,
        release_window_available=(
            reliable_window
        ),
        release_window_start_at=(
            window_start
        ),
        release_window_end_at=(
            window_end
        ),
    )

    return TemporalLiveIntelligence(
        live_turn=live_turn,
        release_window=release_window,
        signal=signal,
    )


def test_direct_capacity_truth_comes_from_t1_profile():
    result = (
        TemporalFutureCapacityCoordinator
        .calculate(
            evaluated_at=NOW,
            direct_capacity=_profile(
                [
                    True,
                    True,
                    False,
                ]
            ),
            live_by_table={},
            seat_capacity_by_table={},
        )
    )

    assert (
        result.capacity.layers[0]
        .directly_available_now
        is True
    )

    assert (
        result.capacity.layers[0]
        .direct_assignment_capacity
        == 4
    )

    assert (
        result.pressure.state
        == TemporalCapacityPressureState.CLEAR
    )


def test_unavailable_current_slot_is_not_direct_capacity():
    result = (
        TemporalFutureCapacityCoordinator
        .calculate(
            evaluated_at=NOW,
            direct_capacity=_profile(
                [
                    False,
                    True,
                    True,
                ]
            ),
            live_by_table={},
            seat_capacity_by_table={},
        )
    )

    assert (
        result.capacity.layers[0]
        .directly_available_now
        is False
    )

    assert (
        result.capacity.layers[0]
        .direct_assignment_capacity
        is None
    )


def test_live_release_becomes_temporal_capacity():
    table_id = uuid4()

    result = (
        TemporalFutureCapacityCoordinator
        .calculate(
            evaluated_at=NOW,
            direct_capacity=_profile(
                [
                    False,
                    False,
                    True,
                ]
            ),
            live_by_table={
                table_id: _live(
                    expected_release_minutes=30,
                )
            },
            seat_capacity_by_table={
                table_id: 4,
            },
        )
    )

    layer_30 = next(
        layer
        for layer in result.capacity.layers
        if layer.horizon_minutes == 30
    )

    assert (
        layer_30.expected_released_tables
        == 1
    )

    assert (
        layer_30.expected_released_seats
        == 4
    )


def test_reliable_window_produces_conservative_release():
    table_id = uuid4()

    result = (
        TemporalFutureCapacityCoordinator
        .calculate(
            evaluated_at=NOW,
            direct_capacity=_profile(
                [
                    False,
                    False,
                    True,
                ]
            ),
            live_by_table={
                table_id: _live(
                    expected_release_minutes=20,
                    reliable_window=True,
                    window_end_minutes=30,
                )
            },
            seat_capacity_by_table={
                table_id: 4,
            },
        )
    )

    layer_30 = next(
        layer
        for layer in result.capacity.layers
        if layer.horizon_minutes == 30
    )

    assert (
        layer_30.conservative_released_tables
        == 1
    )

    assert (
        layer_30.conservative_released_seats
        == 4
    )

    assert (
        result.pressure.state
        == (
            TemporalCapacityPressureState
            .RECOVERING_SOON
        )
    )


def test_unreliable_release_remains_expected_only():
    table_id = uuid4()

    result = (
        TemporalFutureCapacityCoordinator
        .calculate(
            evaluated_at=NOW,
            direct_capacity=_profile(
                [
                    False,
                    False,
                    False,
                ]
            ),
            live_by_table={
                table_id: _live(
                    expected_release_minutes=30,
                    reliable_window=False,
                )
            },
            seat_capacity_by_table={
                table_id: 4,
            },
        )
    )

    assert (
        result.pressure.state
        == (
            TemporalCapacityPressureState
            .UNCERTAIN_RECOVERY
        )
    )


def test_saturation_is_derived_from_t1_slots():
    result = (
        TemporalFutureCapacityCoordinator
        .calculate(
            evaluated_at=NOW,
            direct_capacity=_profile(
                [
                    False,
                    False,
                    False,
                    True,
                    True,
                ]
            ),
            live_by_table={},
            seat_capacity_by_table={},
        )
    )

    assert (
        result.saturation.unavailable_ratio
        == 0.6
    )

    assert (
        result.saturation.state
        == TemporalSaturationState.HIGH
    )


def test_missing_table_capacity_fails_closed():
    table_id = uuid4()

    with pytest.raises(
        ValueError,
        match="Missing seat capacity",
    ):
        (
            TemporalFutureCapacityCoordinator
            .calculate(
                evaluated_at=NOW,
                direct_capacity=_profile(
                    [
                        False,
                        True,
                    ]
                ),
                live_by_table={
                    table_id: _live(
                        expected_release_minutes=30,
                    )
                },
                seat_capacity_by_table={},
            )
        )


def test_invalid_table_capacity_fails_closed():
    table_id = uuid4()

    with pytest.raises(
        ValueError,
        match="must be positive",
    ):
        (
            TemporalFutureCapacityCoordinator
            .calculate(
                evaluated_at=NOW,
                direct_capacity=_profile(
                    [
                        False,
                        True,
                    ]
                ),
                live_by_table={
                    table_id: _live(
                        expected_release_minutes=30,
                    )
                },
                seat_capacity_by_table={
                    table_id: 0,
                },
            )
        )


def test_profile_cannot_start_before_evaluation():
    profile = _profile(
        [
            True,
            True,
        ]
    )

    profile.start_at = (
        NOW
        - timedelta(minutes=30)
    )

    with pytest.raises(
        ValueError,
        match="cannot start before",
    ):
        (
            TemporalFutureCapacityCoordinator
            .calculate(
                evaluated_at=NOW,
                direct_capacity=profile,
                live_by_table={},
                seat_capacity_by_table={},
            )
        )


def test_invalid_peak_period_fails_closed():
    with pytest.raises(
        ValueError,
        match="peak_period_minutes",
    ):
        (
            TemporalFutureCapacityCoordinator
            .calculate(
                evaluated_at=NOW,
                direct_capacity=_profile(
                    [
                        True,
                        True,
                    ]
                ),
                live_by_table={},
                seat_capacity_by_table={},
                peak_period_minutes=0,
            )
        )