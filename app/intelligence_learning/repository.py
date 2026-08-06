from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_learning.models import (
    RestaurantLearningProfile,
)


class RestaurantLearningProfileRepository:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def get_by_restaurant_id(
        self,
        restaurant_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> RestaurantLearningProfile | None:
        statement = select(
            RestaurantLearningProfile
        ).where(
            RestaurantLearningProfile.restaurant_id
            == restaurant_id,
        )

        if for_update:
            statement = statement.with_for_update()

        result = await self.db.execute(
            statement,
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        restaurant_id: uuid.UUID,
    ) -> RestaurantLearningProfile:
        profile = RestaurantLearningProfile(
            restaurant_id=restaurant_id,
            suggestions_created=0,
            suggestions_read=0,
            suggestions_accepted=0,
            suggestions_dismissed=0,
            suggestions_expired=0,
            accepted_score_average=None,
            dismissed_score_average=None,
            accepted_moves_average=None,
            accepted_seat_waste_average=None,
            acceptance_rate=0.0,
            dismissal_rate=0.0,
            read_rate=0.0,
            confidence_score=0.0,
            profile_version=1,
            last_processed_event_id=None,
            last_processed_event_at=None,
            created_at=datetime.now(
                timezone.utc,
            ),
            updated_at=datetime.now(
                timezone.utc,
            ),
        )

        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)

        return profile

    async def save(
        self,
        profile: RestaurantLearningProfile,
    ) -> RestaurantLearningProfile:
        profile.updated_at = datetime.now(
            timezone.utc,
        )

        await self.db.flush()
        await self.db.refresh(profile)

        return profile