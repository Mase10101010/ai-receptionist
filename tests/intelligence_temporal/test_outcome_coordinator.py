from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_temporal.outcome_coordinator import (
    TemporalPredictionOutcomeCoordinator,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionRecord,
)
from app.models.reservation import ReservationStatus


@pytest.mark.asyncio
async def test_records_outcome_for_completed_reservation():
    restaurant_id = uuid4()
    reservation_id = uuid4()

    seated_at = datetime(
        2026,
        9,
        5,
        19,
        0,
        tzinfo=timezone.utc,
    )

    completed_at = (
        seated_at
        + timedelta(minutes=108)
    )

    predicted_at = datetime(
        2026,
        9,
        5,
        18,
        0,
        tzinfo=timezone.utc,
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        table_id=None,
        party_size=4,
        reservation_time=datetime(
            2026,
            9,
            5,
            18,
            45,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.COMPLETED,
        seated_at=seated_at,
        completed_at=completed_at,
    )

    prediction = (
        TemporalTurnPredictionRecord(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            predicted_at=predicted_at,
            expected_duration_minutes=100,
            planned_duration_minutes=90,
            adjustment_minutes=10,
            source=(
                ExpectedTurnSource.PARTY_SIZE
            ),
            source_sample_count=34,
            confidence=(
                ExpectedTurnConfidence.HIGH
            ),
            used_learned_pattern=True,
        )
    )

    prediction_reader = SimpleNamespace(
        latest_for_reservation=AsyncMock(
            return_value=prediction
        )
    )

    event_service = SimpleNamespace(
        record_outcome=AsyncMock()
    )

    coordinator = (
        TemporalPredictionOutcomeCoordinator(
            prediction_reader=prediction_reader,
            event_service=event_service,
        )
    )

    outcome = (
        await coordinator
        .record_for_completed_reservation(
            session=object(),
            reservation=reservation,
        )
    )

    assert outcome is not None

    assert (
        outcome.reservation_id
        == reservation_id
    )

    assert (
        outcome.restaurant_id
        == restaurant_id
    )

    assert (
        outcome.predicted_duration_minutes
        == 100
    )

    assert (
        outcome.actual_duration_minutes
        == 108
    )

    assert (
        outcome.signed_error_minutes
        == 8
    )

    assert (
        outcome.absolute_error_minutes
        == 8
    )

    prediction_reader.latest_for_reservation.assert_awaited_once_with(
        session=ANY,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    event_service.record_outcome.assert_awaited_once_with(
        session=ANY,
        outcome=outcome,
    )


@pytest.mark.asyncio
async def test_missing_prediction_produces_no_outcome():
    restaurant_id = uuid4()
    reservation_id = uuid4()

    seated_at = datetime(
        2026,
        9,
        5,
        19,
        0,
        tzinfo=timezone.utc,
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        table_id=None,
        party_size=2,
        reservation_time=seated_at,
        duration_minutes=90,
        status=ReservationStatus.COMPLETED,
        seated_at=seated_at,
        completed_at=(
            seated_at
            + timedelta(minutes=90)
        ),
    )

    prediction_reader = SimpleNamespace(
        latest_for_reservation=AsyncMock(
            return_value=None
        )
    )

    event_service = SimpleNamespace(
        record_outcome=AsyncMock()
    )

    coordinator = (
        TemporalPredictionOutcomeCoordinator(
            prediction_reader=prediction_reader,
            event_service=event_service,
        )
    )

    outcome = (
        await coordinator
        .record_for_completed_reservation(
            session=object(),
            reservation=reservation,
        )
    )

    assert outcome is None

    event_service.record_outcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_observation_produces_no_outcome():
    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        table_id=None,
        party_size=2,
        reservation_time=datetime(
            2026,
            9,
            5,
            19,
            0,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.COMPLETED,
        seated_at=None,
        completed_at=None,
    )

    prediction_reader = SimpleNamespace(
        latest_for_reservation=AsyncMock()
    )

    event_service = SimpleNamespace(
        record_outcome=AsyncMock()
    )

    coordinator = (
        TemporalPredictionOutcomeCoordinator(
            prediction_reader=prediction_reader,
            event_service=event_service,
        )
    )

    outcome = (
        await coordinator
        .record_for_completed_reservation(
            session=object(),
            reservation=reservation,
        )
    )

    assert outcome is None

    prediction_reader.latest_for_reservation.assert_not_awaited()

    event_service.record_outcome.assert_not_awaited()