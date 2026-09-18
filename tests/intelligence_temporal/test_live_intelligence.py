from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_temporal.live_intelligence import (
    TemporalLiveIntelligenceCoordinator,
)
from app.intelligence_temporal.live_signal import (
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
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionOutcome,
)


EXPECTED_RELEASE = datetime(
    2026,
    9,
    6,
    20,
    40,
    tzinfo=timezone.utc,
)


def _reservation():
    return SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
    )


def _live_turn(
    *,
    remaining_minutes: int = 10,
) -> LiveTurnPrediction:
    return LiveTurnPrediction(
        seated_at=datetime(
            2026,
            9,
            6,
            19,
            0,
            tzinfo=timezone.utc,
        ),
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
        expected_duration_minutes=100,
        expected_release_at=EXPECTED_RELEASE,
        elapsed_minutes=90,
        remaining_minutes=remaining_minutes,
        overrun_minutes=0,
        state=LiveTurnState.IN_PROGRESS,
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


def _outcome(
    *,
    restaurant_id,
    signed_error_minutes: int,
) -> TemporalTurnPredictionOutcome:
    predicted = 100

    return TemporalTurnPredictionOutcome(
        reservation_id=uuid4(),
        restaurant_id=restaurant_id,
        predicted_at=datetime(
            2026,
            8,
            1,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            8,
            1,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        predicted_duration_minutes=predicted,
        actual_duration_minutes=(
            predicted + signed_error_minutes
        ),
        signed_error_minutes=(
            signed_error_minutes
        ),
        absolute_error_minutes=abs(
            signed_error_minutes
        ),
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


def _well_calibrated_outcomes(
    *,
    restaurant_id,
):
    errors = [
        -10,
        -8,
        -6,
        -5,
        -4,
        -3,
        -2,
        -1,
        0,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        8,
        10,
        -2,
        2,
    ]

    return [
        _outcome(
            restaurant_id=restaurant_id,
            signed_error_minutes=error,
        )
        for error in errors
    ]


@pytest.mark.asyncio
async def test_builds_complete_live_intelligence():
    reservation = _reservation()

    live_coordinator = AsyncMock()
    live_coordinator.calculate_for_reservation.return_value = (
        _live_turn()
    )

    outcome_reader = AsyncMock()
    outcome_reader.list_for_restaurant.return_value = (
        _well_calibrated_outcomes(
            restaurant_id=reservation.restaurant_id,
        )
    )

    result = await TemporalLiveIntelligenceCoordinator(
        live_turn_coordinator=live_coordinator,
        outcome_reader=outcome_reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert result is not None

    assert result.live_turn.expected_release_at == (
        EXPECTED_RELEASE
    )

    assert result.release_window.available is True

    assert (
        result.signal.state
        == (
            TemporalLiveSignalState
            .EXPECTED_TO_FREE_SOON
        )
    )


@pytest.mark.asyncio
async def test_reads_historical_outcomes_once():
    reservation = _reservation()

    live_coordinator = AsyncMock()
    live_coordinator.calculate_for_reservation.return_value = (
        _live_turn()
    )

    outcome_reader = AsyncMock()
    outcome_reader.list_for_restaurant.return_value = (
        _well_calibrated_outcomes(
            restaurant_id=reservation.restaurant_id,
        )
    )

    session = object()

    await TemporalLiveIntelligenceCoordinator(
        live_turn_coordinator=live_coordinator,
        outcome_reader=outcome_reader,
    ).calculate_for_reservation(
        session=session,
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
    )

    outcome_reader.list_for_restaurant.assert_awaited_once_with(
        session=session,
        restaurant_id=reservation.restaurant_id,
    )


@pytest.mark.asyncio
async def test_missing_live_turn_fails_closed_without_outcome_read():
    reservation = _reservation()

    live_coordinator = AsyncMock()
    live_coordinator.calculate_for_reservation.return_value = None

    outcome_reader = AsyncMock()

    result = await TemporalLiveIntelligenceCoordinator(
        live_turn_coordinator=live_coordinator,
        outcome_reader=outcome_reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert result is None

    outcome_reader.list_for_restaurant.assert_not_awaited()


@pytest.mark.asyncio
async def test_sparse_history_keeps_point_release_without_window():
    reservation = _reservation()

    live_coordinator = AsyncMock()
    live_coordinator.calculate_for_reservation.return_value = (
        _live_turn()
    )

    outcome_reader = AsyncMock()
    outcome_reader.list_for_restaurant.return_value = [
        _outcome(
            restaurant_id=reservation.restaurant_id,
            signed_error_minutes=5,
        )
        for _ in range(5)
    ]

    result = await TemporalLiveIntelligenceCoordinator(
        live_turn_coordinator=live_coordinator,
        outcome_reader=outcome_reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert result is not None

    assert result.release_window.available is False

    assert (
        result.release_window.expected_release_at
        == EXPECTED_RELEASE
    )

    assert (
        result.signal.expected_release_at
        == EXPECTED_RELEASE
    )


@pytest.mark.asyncio
async def test_unreliable_history_does_not_expose_window():
    reservation = _reservation()

    live_coordinator = AsyncMock()
    live_coordinator.calculate_for_reservation.return_value = (
        _live_turn()
    )

    outcome_reader = AsyncMock()
    outcome_reader.list_for_restaurant.return_value = [
        _outcome(
            restaurant_id=reservation.restaurant_id,
            signed_error_minutes=error,
        )
        for error in (
            [30, -30] * 10
        )
    ]

    result = await TemporalLiveIntelligenceCoordinator(
        live_turn_coordinator=live_coordinator,
        outcome_reader=outcome_reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert result is not None

    assert result.release_window.available is False


@pytest.mark.asyncio
async def test_live_signal_preserves_overrun_state():
    reservation = _reservation()

    overrun = _live_turn(
        remaining_minutes=0,
    ).model_copy(
        update={
            "state": LiveTurnState.OVERRUN,
            "overrun_minutes": 12,
        }
    )

    live_coordinator = AsyncMock()
    live_coordinator.calculate_for_reservation.return_value = (
        overrun
    )

    outcome_reader = AsyncMock()
    outcome_reader.list_for_restaurant.return_value = (
        _well_calibrated_outcomes(
            restaurant_id=reservation.restaurant_id,
        )
    )

    result = await TemporalLiveIntelligenceCoordinator(
        live_turn_coordinator=live_coordinator,
        outcome_reader=outcome_reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            52,
            tzinfo=timezone.utc,
        ),
    )

    assert result is not None

    assert (
        result.signal.state
        == TemporalLiveSignalState.OVERRUN
    )

    assert result.signal.overrun_minutes == 12