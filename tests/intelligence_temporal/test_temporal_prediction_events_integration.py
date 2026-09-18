from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.intelligence_events.models import (
    IntelligenceEvent,
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
from app.models.restaurant import Restaurant
from app.models.user import User


@pytest.mark.asyncio
async def test_temporal_prediction_event_persists_in_postgresql():
    session = AsyncSessionLocal()

    try:
        suffix = uuid4().hex

        user = User(
            email=f"temporal-{suffix}@example.com",
            hashed_password="test",
            is_active=True,
            is_email_verified=True,
        )

        session.add(user)
        await session.flush()

        restaurant = Restaurant(
            owner_id=user.id,
            name=f"Temporal Event Test {suffix}",
            slug=f"temporal-event-{suffix}",
        )

        session.add(restaurant)
        await session.flush()

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
            restaurant_id=restaurant.id,
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

        recorded_event = await service.record_prediction(
            session=session,
            prediction=prediction,
        )

        await session.flush()

        event_id = recorded_event.id

        session.expunge(recorded_event)

        result = await session.execute(
            select(IntelligenceEvent).where(
                IntelligenceEvent.id == event_id,
            )
        )

        persisted_event = result.scalar_one()

        assert (
            persisted_event.event_type
            == IntelligenceEventType.TEMPORAL_TURN_PREDICTED
        )

        assert (
            persisted_event.source
            == IntelligenceEventSource.SYSTEM
        )

        assert persisted_event.restaurant_id == restaurant.id
        assert persisted_event.entity_type == "reservation"
        assert persisted_event.entity_id == reservation_id

        assert persisted_event.event_version == 1

        assert persisted_event.occurred_at == predicted_at
        assert persisted_event.occurred_at.tzinfo is not None

        assert persisted_event.payload == {
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

        assert persisted_event.metadata_json == {
            "service": "temporal_prediction_event_service",
            "event_schema": "temporal_turn_predicted.v1",
        }

    finally:
        await session.rollback()
        await session.close()