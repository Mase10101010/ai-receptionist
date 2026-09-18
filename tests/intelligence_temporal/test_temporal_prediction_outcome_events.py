from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
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
from app.intelligence_temporal.outcome_events import (
    TemporalPredictionOutcomeEventService,
)


@pytest.mark.asyncio
async def test_records_temporal_prediction_outcome(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    predicted_at = datetime(
        2026,
        9,
        5,
        18,
        0,
        tzinfo=timezone.utc,
    )

    completed_at = datetime(
        2026,
        9,
        5,
        19,
        48,
        tzinfo=timezone.utc,
    )

    outcome = SimpleNamespace(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        predicted_at=predicted_at,
        completed_at=completed_at,
        predicted_duration_minutes=100,
        actual_duration_minutes=108,
        signed_error_minutes=8,
        absolute_error_minutes=8,
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=34,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )

    record = AsyncMock(
        return_value=SimpleNamespace()
    )

    class FakeEventService:
        def __init__(self, repository):
            self.repository = repository

        async def record(self, **kwargs):
            return await record(**kwargs)

    monkeypatch.setattr(
        "app.intelligence_temporal.outcome_events."
        "IntelligenceEventService",
        FakeEventService,
    )

    result = await (
        TemporalPredictionOutcomeEventService()
        .record_outcome(
            session=object(),
            outcome=outcome,
        )
    )

    assert result is not None

    record.assert_awaited_once_with(
        restaurant_id=restaurant_id,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ),
        source=IntelligenceEventSource.SYSTEM,
        entity_type="reservation",
        entity_id=reservation_id,
        event_version=1,
        payload={
            "reservation_id": str(
                reservation_id
            ),
            "predicted_at": (
                predicted_at.isoformat()
            ),
            "predicted_duration_minutes": 100,
            "actual_duration_minutes": 108,
            "signed_error_minutes": 8,
            "absolute_error_minutes": 8,
            "source": (
                ExpectedTurnSource.PARTY_SIZE.value
            ),
            "source_sample_count": 34,
            "confidence": (
                ExpectedTurnConfidence.HIGH.value
            ),
            "used_learned_pattern": True,
        },
        metadata={
            "service": (
                "temporal_prediction_outcome_event_service"
            ),
            "event_schema": (
                "temporal_turn_outcome_recorded.v1"
            ),
        },
        occurred_at=completed_at,
    )