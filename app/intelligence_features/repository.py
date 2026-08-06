from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventType,
)


class IntelligenceFeatureRepository:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def get_ai_suggestion_metrics(
        self,
        *,
        restaurant_id: uuid.UUID,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> dict[str, int | float | None]:
        statement = select(
            func.count()
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_CREATED
            )
            .label("suggestions_created"),

            func.count()
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_READ
            )
            .label("suggestions_read"),

            func.count()
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_ACCEPTED
            )
            .label("suggestions_accepted"),

            func.count()
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_DISMISSED
            )
            .label("suggestions_dismissed"),

            func.count()
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_EXPIRED
            )
            .label("suggestions_expired"),

            func.avg(
                cast(
                    IntelligenceEvent.payload[
                        "score"
                    ].as_string(),
                    Float,
                )
            )
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_CREATED
            )
            .label("average_created_score"),

            func.avg(
                cast(
                    IntelligenceEvent.payload[
                        "score"
                    ].as_string(),
                    Float,
                )
            )
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_ACCEPTED
            )
            .label("average_accepted_score"),

            func.avg(
                cast(
                    IntelligenceEvent.payload[
                        "score"
                    ].as_string(),
                    Float,
                )
            )
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_DISMISSED
            )
            .label("average_dismissed_score"),

            func.avg(
                cast(
                    IntelligenceEvent.payload[
                        "score"
                    ].as_string(),
                    Float,
                )
            )
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_EXPIRED
            )
            .label("average_expired_score"),

            func.avg(
                cast(
                    IntelligenceEvent.payload[
                        "moved_reservations_count"
                    ].as_string(),
                    Float,
                )
            )
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_ACCEPTED
            )
            .label("average_moves_accepted"),

            func.avg(
                cast(
                    IntelligenceEvent.payload[
                        "total_seat_waste"
                    ].as_string(),
                    Float,
                )
            )
            .filter(
                IntelligenceEvent.event_type
                == IntelligenceEventType.AI_SUGGESTION_ACCEPTED
            )
            .label(
                "average_seat_waste_accepted"
            ),
        ).where(
            IntelligenceEvent.restaurant_id
            == restaurant_id,
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

        row = result.one()

        return {
            "suggestions_created": int(
                row.suggestions_created or 0
            ),
            "suggestions_read": int(
                row.suggestions_read or 0
            ),
            "suggestions_accepted": int(
                row.suggestions_accepted or 0
            ),
            "suggestions_dismissed": int(
                row.suggestions_dismissed or 0
            ),
            "suggestions_expired": int(
                row.suggestions_expired or 0
            ),
            "average_created_score": (
                float(row.average_created_score)
                if row.average_created_score
                is not None
                else None
            ),
            "average_accepted_score": (
                float(row.average_accepted_score)
                if row.average_accepted_score
                is not None
                else None
            ),
            "average_dismissed_score": (
                float(row.average_dismissed_score)
                if row.average_dismissed_score
                is not None
                else None
            ),
            "average_expired_score": (
                float(row.average_expired_score)
                if row.average_expired_score
                is not None
                else None
            ),
            "average_moves_accepted": (
                float(row.average_moves_accepted)
                if row.average_moves_accepted
                is not None
                else None
            ),
            "average_seat_waste_accepted": (
                float(
                    row.average_seat_waste_accepted
                )
                if row.average_seat_waste_accepted
                is not None
                else None
            ),
        }