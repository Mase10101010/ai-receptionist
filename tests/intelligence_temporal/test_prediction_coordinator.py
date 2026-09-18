from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_coordinator import (
    TemporalTurnPredictionCoordinator,
)
from app.intelligence_temporal.snapshot import (
    TemporalLearningSnapshot,
)


@pytest.mark.asyncio
async def test_coordinates_planned_fallback_prediction():
    restaurant_id = uuid4()
    reservation_id = uuid4()

    reservation_time = datetime(
        2026,
        9,
        4,
        19,
        30,
        tzinfo=timezone.utc,
    )

    predicted_at = datetime(
        2026,
        9,
        4,
        10,
        30,
        tzinfo=timezone.utc,
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        table_id=None,
        party_size=4,
        duration_minutes=90,
        reservation_time=reservation_time,
    )

    snapshot_service = SimpleNamespace(
        build=AsyncMock(
            return_value=TemporalLearningSnapshot(
                restaurant_id=restaurant_id,
                generated_from_sample_count=0,
            )
        )
    )

    event_service = SimpleNamespace(
        record_prediction=AsyncMock()
    )

    coordinator = TemporalTurnPredictionCoordinator(
        snapshot_service=snapshot_service,
        event_service=event_service,
    )

    record = await coordinator.predict_for_reservation(
        session=object(),
        reservation=reservation,
        predicted_at=predicted_at,
    )

    assert record.reservation_id == reservation_id
    assert record.restaurant_id == restaurant_id
    assert record.predicted_at == predicted_at

    assert record.expected_duration_minutes == 90
    assert record.planned_duration_minutes == 90
    assert record.adjustment_minutes == 0

    assert (
        record.source
        == ExpectedTurnSource.PLANNED_FALLBACK
    )
    assert record.source_sample_count is None
    assert record.confidence == ExpectedTurnConfidence.LOW
    assert record.used_learned_pattern is False

    snapshot_service.build.assert_awaited_once_with(
        session=ANY,
        restaurant_id=restaurant_id,
    )

    event_service.record_prediction.assert_awaited_once_with(
        session=ANY,
        prediction=record,
    )


@pytest.mark.asyncio
async def test_uses_primary_table_service_area():
    restaurant_id = uuid4()
    reservation_id = uuid4()
    table_id = uuid4()
    service_area_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        table_id=table_id,
        party_size=2,
        duration_minutes=90,
        reservation_time=datetime(
            2026,
            9,
            4,
            20,
            0,
            tzinfo=timezone.utc,
        ),
    )

    snapshot_service = SimpleNamespace(
        build=AsyncMock(
            return_value=TemporalLearningSnapshot(
                restaurant_id=restaurant_id,
                generated_from_sample_count=0,
            )
        )
    )

    event_service = SimpleNamespace(
        record_prediction=AsyncMock()
    )

    coordinator = TemporalTurnPredictionCoordinator(
        snapshot_service=snapshot_service,
        event_service=event_service,
    )

    coordinator._service_area_id = AsyncMock(
        return_value=service_area_id
    )

    await coordinator.predict_for_reservation(
        session=object(),
        reservation=reservation,
    )

    coordinator._service_area_id.assert_awaited_once_with(
        session=ANY,
        table_id=table_id,
    )

    event_service.record_prediction.assert_awaited_once()