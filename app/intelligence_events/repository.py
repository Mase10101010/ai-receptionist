from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventType,
)


class IntelligenceEventRepository:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def create(
        self,
        event: IntelligenceEvent,
    ) -> IntelligenceEvent:
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)

        return event

    async def get_by_id(
        self,
        event_id: uuid.UUID,
    ) -> IntelligenceEvent | None:
        result = await self.db.execute(
            select(IntelligenceEvent).where(
                IntelligenceEvent.id
                == event_id,
            )
        )

        return result.scalar_one_or_none()

    async def list_for_restaurant(
        self,
        restaurant_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        event_type: IntelligenceEventType | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> list[IntelligenceEvent]:
        statement = (
            select(IntelligenceEvent)
            .where(
                IntelligenceEvent.restaurant_id
                == restaurant_id,
            )
            .order_by(
                IntelligenceEvent.occurred_at.desc(),
                IntelligenceEvent.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        if event_type is not None:
            statement = statement.where(
                IntelligenceEvent.event_type
                == event_type,
            )

        if entity_type is not None:
            statement = statement.where(
                IntelligenceEvent.entity_type
                == entity_type,
            )

        if entity_id is not None:
            statement = statement.where(
                IntelligenceEvent.entity_id
                == entity_id,
            )

        if occurred_after is not None:
            statement = statement.where(
                IntelligenceEvent.occurred_at
                >= occurred_after,
            )

        if occurred_before is not None:
            statement = statement.where(
                IntelligenceEvent.occurred_at
                <= occurred_before,
            )

        result = await self.db.execute(
            statement,
        )

        return list(
            result.scalars().all(),
        )

    async def list_after_cursor(
        self,
        *,
        restaurant_id: uuid.UUID,
        created_after: datetime | None = None,
        last_event_id: uuid.UUID | None = None,
        limit: int = 500,
    ) -> list[IntelligenceEvent]:
        statement = select(
            IntelligenceEvent
        ).where(
            IntelligenceEvent.restaurant_id
            == restaurant_id,
        )

        if created_after is not None:
            statement = statement.where(
                IntelligenceEvent.created_at
                > created_after,
            )

        statement = (
            statement
            .order_by(
                IntelligenceEvent.created_at.asc(),
                IntelligenceEvent.id.asc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(
            statement,
        )

        return list(
            result.scalars().all(),
        )

    async def list_for_entity(
        self,
        *,
        restaurant_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 100,
    ) -> list[IntelligenceEvent]:
        result = await self.db.execute(
            select(IntelligenceEvent)
            .where(
                IntelligenceEvent.restaurant_id
                == restaurant_id,
                IntelligenceEvent.entity_type
                == entity_type,
                IntelligenceEvent.entity_id
                == entity_id,
            )
            .order_by(
                IntelligenceEvent.occurred_at.desc(),
                IntelligenceEvent.created_at.desc(),
            )
            .limit(limit)
        )

        return list(
            result.scalars().all(),
        )