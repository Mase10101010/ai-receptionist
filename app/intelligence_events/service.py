from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_events.schemas import (
    IntelligenceEventCreate,
)


class IntelligenceEventService:
    def __init__(
        self,
        repository: IntelligenceEventRepository,
    ) -> None:
        self.repository = repository

    async def record(
        self,
        *,
        restaurant_id: uuid.UUID,
        event_type: IntelligenceEventType,
        source: IntelligenceEventSource,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        correlation_id: uuid.UUID | None = None,
        causation_event_id: uuid.UUID | None = None,
        event_version: int = 1,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> IntelligenceEvent:
        event = IntelligenceEvent(
            restaurant_id=restaurant_id,
            event_type=event_type,
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            correlation_id=(
                correlation_id
                or uuid.uuid4()
            ),
            causation_event_id=causation_event_id,
            event_version=event_version,
            payload=payload or {},
            metadata_json=metadata or {},
            occurred_at=(
                occurred_at
                or datetime.now(timezone.utc)
            ),
        )

        return await self.repository.create(
            event,
        )

    async def record_from_schema(
        self,
        payload: IntelligenceEventCreate,
    ) -> IntelligenceEvent:
        return await self.record(
            restaurant_id=payload.restaurant_id,
            event_type=payload.event_type,
            source=payload.source,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            actor_user_id=payload.actor_user_id,
            correlation_id=payload.correlation_id,
            causation_event_id=(
                payload.causation_event_id
            ),
            event_version=payload.event_version,
            payload=payload.payload,
            metadata=payload.metadata,
            occurred_at=payload.occurred_at,
        )

    async def get_event(
        self,
        event_id: uuid.UUID,
    ) -> IntelligenceEvent | None:
        return await self.repository.get_by_id(
            event_id,
        )

    async def list_restaurant_events(
        self,
        *,
        restaurant_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
        event_type: IntelligenceEventType | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> list[IntelligenceEvent]:
        return (
            await self.repository
            .list_for_restaurant(
                restaurant_id=restaurant_id,
                limit=limit,
                offset=offset,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                occurred_after=occurred_after,
                occurred_before=occurred_before,
            )
        )