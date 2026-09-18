from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.reservation import ReservationStatus

from app.intelligence_temporal.live_turn import (
    LiveTurnState,
)
from app.intelligence_temporal.live_turn_coordinator import (
    LiveTurnCoordinator,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionRecord,
)


def _reservation(
    *,
    status=ReservationStatus.SEATED,
    seated_at=None,
    restaurant_id=None,
):
    return SimpleNamespace(
        id=uuid4(),
        restaurant_id=(
            restaurant_id or uuid4()
        ),
        status=status,
        seated_at=(
            seated_at
            or datetime(
                2026,
                9,
                6,
                19,
                0,
                tzinfo=timezone.utc,
            )
        ),
    )


def _prediction_record(
    *,
    reservation_id,
    restaurant_id,
    expected_duration_minutes=100,
):
    return TemporalTurnPredictionRecord(
        reservation_id=reservation_id,
        restaurant_id=restaurant_id,
        predicted_at=datetime(
            2026,
            9,
            6,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        expected_duration_minutes=(
            expected_duration_minutes
        ),
        planned_duration_minutes=90,
        adjustment_minutes=(
            expected_duration_minutes - 90
        ),
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


@pytest.mark.asyncio
async def test_builds_live_turn_from_original_prediction():
    reservation = _reservation()

    reader = AsyncMock()
    reader.latest_for_reservation.return_value = (
        _prediction_record(
            reservation_id=reservation.id,
            restaurant_id=(
                reservation.restaurant_id
            ),
        )
    )

    live = await LiveTurnCoordinator(
        prediction_reader=reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            19,
            35,
            tzinfo=timezone.utc,
        ),
    )

    assert live is not None

    assert live.expected_duration_minutes == 100

    assert live.expected_release_at == datetime(
        2026,
        9,
        6,
        20,
        40,
        tzinfo=timezone.utc,
    )

    assert live.elapsed_minutes == 35
    assert live.remaining_minutes == 65
    assert live.overrun_minutes == 0

    assert live.state == LiveTurnState.IN_PROGRESS

    assert (
        live.source
        == ExpectedTurnSource.PARTY_SIZE
    )

    assert (
        live.confidence
        == ExpectedTurnConfidence.HIGH
    )


@pytest.mark.asyncio
async def test_reads_prediction_for_exact_reservation():
    reservation = _reservation()

    reader = AsyncMock()
    reader.latest_for_reservation.return_value = (
        _prediction_record(
            reservation_id=reservation.id,
            restaurant_id=(
                reservation.restaurant_id
            ),
        )
    )

    session = object()

    await LiveTurnCoordinator(
        prediction_reader=reader,
    ).calculate_for_reservation(
        session=session,
        reservation=reservation,
        evaluated_at=reservation.seated_at,
    )

    reader.latest_for_reservation.assert_awaited_once_with(
        session=session,
        restaurant_id=reservation.restaurant_id,
        reservation_id=reservation.id,
    )


@pytest.mark.asyncio
async def test_non_seated_reservation_is_not_eligible():
    reservation = _reservation(
        status=ReservationStatus.CONFIRMED,
    )

    reader = AsyncMock()

    live = await LiveTurnCoordinator(
        prediction_reader=reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            19,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert live is None

    reader.latest_for_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_seated_at_is_not_eligible():
    reservation = _reservation()

    reservation.seated_at = None

    reader = AsyncMock()

    live = await LiveTurnCoordinator(
        prediction_reader=reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            19,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert live is None

    reader.latest_for_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_prediction_fails_closed():
    reservation = _reservation()

    reader = AsyncMock()
    reader.latest_for_reservation.return_value = None

    live = await LiveTurnCoordinator(
        prediction_reader=reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=datetime(
            2026,
            9,
            6,
            19,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert live is None


@pytest.mark.asyncio
async def test_original_prediction_provenance_is_preserved():
    reservation = _reservation()

    reader = AsyncMock()
    reader.latest_for_reservation.return_value = (
        _prediction_record(
            reservation_id=reservation.id,
            restaurant_id=(
                reservation.restaurant_id
            ),
            expected_duration_minutes=115,
        )
    )

    live = await LiveTurnCoordinator(
        prediction_reader=reader,
    ).calculate_for_reservation(
        session=object(),
        reservation=reservation,
        evaluated_at=reservation.seated_at,
    )

    assert live is not None

    assert live.expected_duration_minutes == 115
    assert live.source_sample_count == 30
    assert live.used_learned_pattern is True

    assert (
        live.source
        == ExpectedTurnSource.PARTY_SIZE
    )

    assert (
        live.confidence
        == ExpectedTurnConfidence.HIGH
    )