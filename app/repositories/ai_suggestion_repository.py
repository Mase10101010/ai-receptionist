from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_suggestion import (
    AISuggestion,
    AISuggestionStatus,
)


class AISuggestionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        suggestion: AISuggestion,
    ) -> AISuggestion:
        self.db.add(suggestion)
        await self.db.flush()
        await self.db.refresh(suggestion)
        return suggestion

    async def get_by_id(
        self,
        suggestion_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID] | None = None,
    ) -> AISuggestion | None:
        query = select(AISuggestion).where(
            AISuggestion.id == suggestion_id,
        )

        if restaurant_ids is not None:
            query = query.where(
                AISuggestion.restaurant_id.in_(
                    restaurant_ids,
                ),
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_pending(
        self,
        restaurant_ids: list[uuid.UUID],
        limit: int = 50,
    ) -> list[AISuggestion]:
        if not restaurant_ids:
            return []

        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(AISuggestion)
            .where(
                AISuggestion.restaurant_id.in_(
                    restaurant_ids,
                ),
                AISuggestion.status
                == AISuggestionStatus.PENDING,
                (
                    AISuggestion.expires_at.is_(None)
                    | (AISuggestion.expires_at > now)
                ),
            )
            .order_by(
                AISuggestion.created_at.desc(),
            )
            .limit(limit)
        )

        return list(result.scalars().all())

    async def find_pending_for_reservation(
        self,
        reservation_id: uuid.UUID,
    ) -> AISuggestion | None:
        result = await self.db.execute(
            select(AISuggestion)
            .where(
                AISuggestion.reservation_id
                == reservation_id,
                AISuggestion.status
                == AISuggestionStatus.PENDING,
            )
            .order_by(
                AISuggestion.created_at.desc(),
            )
            .limit(1)
        )

        return result.scalar_one_or_none()

    async def update_status(
        self,
        suggestion: AISuggestion,
        status: AISuggestionStatus,
    ) -> AISuggestion:
        suggestion.status = status
        suggestion.updated_at = datetime.now(
            timezone.utc,
        )

        await self.db.flush()
        await self.db.refresh(suggestion)

        return suggestion

    async def mark_read(
        self,
        suggestion: AISuggestion,
    ) -> AISuggestion:
        suggestion.is_read = True
        suggestion.updated_at = datetime.now(
            timezone.utc,
        )

        await self.db.flush()
        await self.db.refresh(suggestion)

        return suggestion

    async def expire_pending_for_reservation(
        self,
        reservation_id: uuid.UUID,
    ) -> list[AISuggestion]:
        result = await self.db.execute(
            select(AISuggestion)
            .where(
                AISuggestion.reservation_id
                == reservation_id,
                AISuggestion.status
                == AISuggestionStatus.PENDING,
            )
            .order_by(
                AISuggestion.created_at.asc(),
            )
        )

        suggestions = list(
            result.scalars().all(),
        )

        now = datetime.now(timezone.utc)

        for suggestion in suggestions:
            suggestion.status = (
                AISuggestionStatus.EXPIRED
            )
            suggestion.updated_at = now

        if suggestions:
            await self.db.flush()

        return suggestions

    async def expire_pending_for_restaurant(
        self,
        restaurant_id: uuid.UUID,
    ) -> list[AISuggestion]:
        result = await self.db.execute(
            select(AISuggestion)
            .where(
                AISuggestion.restaurant_id
                == restaurant_id,
                AISuggestion.status
                == AISuggestionStatus.PENDING,
            )
            .order_by(
                AISuggestion.created_at.asc(),
            )
        )

        suggestions = list(
            result.scalars().all(),
        )

        now = datetime.now(timezone.utc)

        for suggestion in suggestions:
            suggestion.status = (
                AISuggestionStatus.EXPIRED
            )
            suggestion.updated_at = now

        if suggestions:
            await self.db.flush()

        return suggestions