from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_events.models import (
    IntelligenceEventType,
)
from app.intelligence_temporal.outcome_reader import (
    TemporalOutcomeEventReader,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)


def _event(
    *,
    restaurant_id,
    reservation_id,
    predicted_at,
    completed_at,
    predicted_duration_minutes=100,
    actual_duration_minutes=108,
):
    signed_error = (
        actual_duration_minutes
        - predicted_duration_minutes
    )

    return SimpleNamespace(
        restaurant_id=restaurant_id,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ),
        entity_type="reservation",
        entity_id=reservation_id,
        occurred_at=completed_at,
        payload={
            "reservation_id": str(
                reservation_id
            ),
            "predicted_at": (
                predicted_at.isoformat()
            ),
            "predicted_duration_minutes": (
                predicted_duration_minutes
            ),
            "actual_duration_minutes": (
                actual_duration_minutes
            ),
            "signed_error_minutes": (
                signed_error
            ),
            "absolute_error_minutes": abs(
                signed_error
            ),
            "source": (
                ExpectedTurnSource
                .PARTY_SIZE
                .value
            ),
            "source_sample_count": 34,
            "confidence": (
                ExpectedTurnConfidence
                .HIGH
                .value
            ),
            "used_learned_pattern": True,
        },
    )


@pytest.mark.asyncio
async def test_lists_typed_outcomes_for_restaurant(
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

    event = _event(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        predicted_at=predicted_at,
        completed_at=completed_at,
    )

    list_for_restaurant = AsyncMock(
        return_value=[event],
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
        "outcome_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    session = object()

    outcomes = await (
        TemporalOutcomeEventReader()
        .list_for_restaurant(
            session=session,
            restaurant_id=restaurant_id,
        )
    )

    assert len(outcomes) == 1

    outcome = outcomes[0]

    assert (
        outcome.reservation_id
        == reservation_id
    )
    assert (
        outcome.restaurant_id
        == restaurant_id
    )
    assert outcome.predicted_at == predicted_at
    assert outcome.completed_at == completed_at

    assert (
        outcome.predicted_duration_minutes
        == 100
    )
    assert outcome.actual_duration_minutes == 108
    assert outcome.signed_error_minutes == 8
    assert outcome.absolute_error_minutes == 8

    assert (
        outcome.source
        == ExpectedTurnSource.PARTY_SIZE
    )
    assert outcome.source_sample_count == 34
    assert (
        outcome.confidence
        == ExpectedTurnConfidence.HIGH
    )
    assert outcome.used_learned_pattern is True

    list_for_restaurant.assert_awaited_once_with(
        restaurant_id=restaurant_id,
        limit=1000,
        offset=0,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ),
        occurred_after=None,
        occurred_before=None,
    )


@pytest.mark.asyncio
async def test_applies_time_range_and_pagination(
    monkeypatch,
):
    restaurant_id = uuid4()

    occurred_after = datetime(
        2026,
        8,
        1,
        tzinfo=timezone.utc,
    )

    occurred_before = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    list_for_restaurant = AsyncMock(
        return_value=[],
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
        "outcome_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    await (
        TemporalOutcomeEventReader()
        .list_for_restaurant(
            session=object(),
            restaurant_id=restaurant_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
            limit=250,
            offset=50,
        )
    )

    list_for_restaurant.assert_awaited_once_with(
        restaurant_id=restaurant_id,
        limit=250,
        offset=50,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ),
        occurred_after=occurred_after,
        occurred_before=occurred_before,
    )


@pytest.mark.asyncio
async def test_malformed_outcome_is_skipped(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    malformed_event = SimpleNamespace(
        restaurant_id=restaurant_id,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ),
        entity_type="reservation",
        entity_id=reservation_id,
        occurred_at=datetime.now(
            timezone.utc
        ),
        payload={
            "reservation_id": str(
                reservation_id
            ),
            # predicted_at intentionally missing
            "predicted_duration_minutes": 90,
        },
    )

    valid_reservation_id = uuid4()

    completed_at = datetime(
        2026,
        9,
        5,
        20,
        0,
        tzinfo=timezone.utc,
    )

    valid_event = _event(
        restaurant_id=restaurant_id,
        reservation_id=valid_reservation_id,
        predicted_at=(
            completed_at
            - timedelta(minutes=120)
        ),
        completed_at=completed_at,
    )

    class FakeRepository:
        def __init__(self, session):
            self.session = session

        async def list_for_restaurant(
            self,
            **kwargs,
        ):
            return [
                malformed_event,
                valid_event,
            ]

    monkeypatch.setattr(
        "app.intelligence_temporal."
        "outcome_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    outcomes = await (
        TemporalOutcomeEventReader()
        .list_for_restaurant(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert len(outcomes) == 1
    assert (
        outcomes[0].reservation_id
        == valid_reservation_id
    )


@pytest.mark.asyncio
async def test_mismatched_reservation_identity_is_skipped(
    monkeypatch,
):
    restaurant_id = uuid4()

    entity_reservation_id = uuid4()
    payload_reservation_id = uuid4()

    event = SimpleNamespace(
        restaurant_id=restaurant_id,
        event_type=(
            IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ),
        entity_type="reservation",
        entity_id=entity_reservation_id,
        occurred_at=datetime.now(
            timezone.utc
        ),
        payload={
            "reservation_id": str(
                payload_reservation_id
            ),
            "predicted_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "predicted_duration_minutes": 90,
            "actual_duration_minutes": 100,
            "signed_error_minutes": 10,
            "absolute_error_minutes": 10,
            "source": (
                ExpectedTurnSource
                .PARTY_SIZE
                .value
            ),
            "source_sample_count": 20,
            "confidence": (
                ExpectedTurnConfidence
                .MEDIUM
                .value
            ),
            "used_learned_pattern": True,
        },
    )

    class FakeRepository:
        def __init__(self, session):
            self.session = session

        async def list_for_restaurant(
            self,
            **kwargs,
        ):
            return [event]

    monkeypatch.setattr(
        "app.intelligence_temporal."
        "outcome_reader."
        "IntelligenceEventRepository",
        FakeRepository,
    )

    outcomes = await (
        TemporalOutcomeEventReader()
        .list_for_restaurant(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert outcomes == []