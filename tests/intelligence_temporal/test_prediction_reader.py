from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_events.models import (
    IntelligenceEventType,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_reader import (
    TemporalPredictionEventReader,
)


@pytest.mark.asyncio
async def test_reads_latest_prediction_for_reservation(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    predicted_at = datetime(
        2026,
        9,
        4,
        19,
        0,
        tzinfo=timezone.utc,
    )

    event = SimpleNamespace(
        payload={
            "reservation_id": str(
                reservation_id
            ),
            "predicted_at": (
                predicted_at.isoformat()
            ),
            "expected_duration_minutes": 105,
            "planned_duration_minutes": 90,
            "adjustment_minutes": 15,
            "source": "party_size",
            "source_sample_count": 32,
            "confidence": "high",
            "used_learned_pattern": True,
        }
    )

    list_for_restaurant = AsyncMock(
        return_value=[event]
    )

    class FakeRepository:
        def __init__(self, session):
            self.session = session

        async def list_for_restaurant(
            self,
            **kwargs,
        ):
            return await list_for_restaurant(
                **kwargs
            )

    monkeypatch.setattr(
        "app.intelligence_temporal."
        "prediction_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    session = object()

    record = await (
        TemporalPredictionEventReader()
        .latest_for_reservation(
            session=session,
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
        )
    )

    assert record is not None
    assert record.reservation_id == reservation_id
    assert record.restaurant_id == restaurant_id
    assert record.predicted_at == predicted_at
    assert record.expected_duration_minutes == 105
    assert record.planned_duration_minutes == 90
    assert record.adjustment_minutes == 15

    assert (
        record.source
        == ExpectedTurnSource.PARTY_SIZE
    )
    assert record.source_sample_count == 32
    assert (
        record.confidence
        == ExpectedTurnConfidence.HIGH
    )
    assert record.used_learned_pattern is True

    list_for_restaurant.assert_awaited_once_with(
        restaurant_id=restaurant_id,
        limit=1,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_PREDICTED
        ),
        entity_type="reservation",
        entity_id=reservation_id,
    )


@pytest.mark.asyncio
async def test_returns_none_when_prediction_missing(
    monkeypatch,
):
    class FakeRepository:
        def __init__(self, session):
            pass

        async def list_for_restaurant(
            self,
            **kwargs,
        ):
            return []

    monkeypatch.setattr(
        "app.intelligence_temporal."
        "prediction_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    record = await (
        TemporalPredictionEventReader()
        .latest_for_reservation(
            session=object(),
            restaurant_id=uuid4(),
            reservation_id=uuid4(),
        )
    )

    assert record is None


@pytest.mark.asyncio
async def test_returns_none_for_invalid_payload(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    event = SimpleNamespace(
        payload={
            "reservation_id": str(
                reservation_id
            ),
            # predicted_at intentionally missing
        }
    )

    class FakeRepository:
        def __init__(self, session):
            pass

        async def list_for_restaurant(
            self,
            **kwargs,
        ):
            return [event]

    monkeypatch.setattr(
        "app.intelligence_temporal."
        "prediction_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    record = await (
        TemporalPredictionEventReader()
        .latest_for_reservation(
            session=object(),
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
        )
    )

    assert record is None