from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventType,
)


class IntelligenceCalibrationRepository:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def list_evaluated_predictions(
        self,
        *,
        restaurant_id: uuid.UUID,
        limit: int = 1000,
    ) -> list[IntelligenceEvent]:
        statement = (
            select(IntelligenceEvent)
            .where(
                IntelligenceEvent.restaurant_id
                == restaurant_id,
                IntelligenceEvent.event_type.in_(
                    [
                        IntelligenceEventType
                        .AI_SUGGESTION_ACCEPTED,
                        IntelligenceEventType
                        .AI_SUGGESTION_DISMISSED,
                    ]
                ),
            )
            .order_by(
                IntelligenceEvent.occurred_at.desc(),
                IntelligenceEvent.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(
            statement,
        )

        events = list(
            result.scalars().all()
        )

        return [
            event
            for event in events
            if (
                event.payload.get(
                    "predicted_acceptance_probability"
                )
                is not None
                and event.payload.get(
                    "calibration_actual_value"
                )
                is not None
                and event.payload.get(
                    "calibration_squared_error"
                )
                is not None
            )
        ]