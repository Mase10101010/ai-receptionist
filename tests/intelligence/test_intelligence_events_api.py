from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_events.schemas import (
    IntelligenceEventResponse,
)


def test_intelligence_event_response_serializes():
    event = SimpleNamespace(
        id=uuid.uuid4(),
        restaurant_id=uuid.uuid4(),
        event_type=(
            IntelligenceEventType
            .SEATING_PLAN_APPLIED
        ),
        source=(
            IntelligenceEventSource.MANAGER
        ),
        entity_type="reservation",
        entity_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        causation_event_id=None,
        event_version=1,
        payload={
            "suggestion_id": str(
                uuid.uuid4()
            ),
            "applied": True,
        },
        metadata_json={},
        occurred_at=datetime.now(
            timezone.utc,
        ),
        created_at=datetime.now(
            timezone.utc,
        ),
    )

    response = (
        IntelligenceEventResponse
        .model_validate(event)
    )

    assert (
        response.event_type
        == IntelligenceEventType
        .SEATING_PLAN_APPLIED
    )

    assert (
        response.source
        == IntelligenceEventSource.MANAGER
    )

    assert (
        response.entity_type
        == "reservation"
    )

    assert (
        response.payload["applied"]
        is True
    )