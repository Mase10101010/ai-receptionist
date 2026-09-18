from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_events import (
    TemporalPredictionEventService,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionRecord,
)


@pytest.mark.asyncio
async def test_records_temporal_prediction_event(
    db_session,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    predicted_at = datetime(
        2026,
        9,
        4,
        19,
        30,
        tzinfo=timezone.utc,
    )

    prediction = TemporalTurnPredictionRecord(
        reservation_id=reservation_id,
        restaurant_id=restaurant_id,
        predicted_at=predicted_at,
        expected_duration_minutes=105,
        planned_duration_minutes=90,
        adjustment_minutes=15,
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=12,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )

    service = TemporalPredictionEventService()

    event = await service.record_prediction(
        session=db_session,
        prediction=prediction,
    )

    assert (
        event.event_type
        == IntelligenceEventType.TEMPORAL_TURN_PREDICTED
    )
    assert event.source == IntelligenceEventSource.SYSTEM

    assert event.restaurant_id == restaurant_id
    assert event.entity_type == "reservation"
    assert event.entity_id == reservation_id

    assert event.event_version == 1
    persisted_occurred_at = event.occurred_at

    if persisted_occurred_at.tzinfo is None:
        persisted_occurred_at = persisted_occurred_at.replace(
            tzinfo=timezone.utc,
        )

    assert persisted_occurred_at == predicted_at

    assert event.payload == {
        "reservation_id": str(reservation_id),
        "predicted_at": predicted_at.isoformat(),
        "expected_duration_minutes": 105,
        "planned_duration_minutes": 90,
        "adjustment_minutes": 15,
        "source": ExpectedTurnSource.PARTY_SIZE.value,
        "source_sample_count": 12,
        "confidence": ExpectedTurnConfidence.HIGH.value,
        "used_learned_pattern": True,
    }

    assert event.metadata_json == {
        "service": "temporal_prediction_event_service",
        "event_schema": "temporal_turn_predicted.v1",
    }