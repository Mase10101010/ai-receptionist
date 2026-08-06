from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_features.repository import (
    IntelligenceFeatureRepository,
)
from app.intelligence_features.schemas import (
    AISuggestionFeatures,
)


class IntelligenceFeatureService:
    def __init__(
        self,
        repository: IntelligenceFeatureRepository,
    ) -> None:
        self.repository = repository

    async def get_ai_suggestion_features(
        self,
        *,
        restaurant_id: uuid.UUID,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> AISuggestionFeatures:
        metrics = (
            await self.repository
            .get_ai_suggestion_metrics(
                restaurant_id=restaurant_id,
                occurred_after=occurred_after,
                occurred_before=occurred_before,
            )
        )

        created = int(
            metrics["suggestions_created"] or 0
        )
        read = int(
            metrics["suggestions_read"] or 0
        )
        accepted = int(
            metrics["suggestions_accepted"] or 0
        )
        dismissed = int(
            metrics["suggestions_dismissed"] or 0
        )
        expired = int(
            metrics["suggestions_expired"] or 0
        )

        acceptance_rate = (
            accepted / created
            if created > 0
            else 0.0
        )

        dismissal_rate = (
            dismissed / created
            if created > 0
            else 0.0
        )

        read_rate = (
            read / created
            if created > 0
            else 0.0
        )

        return AISuggestionFeatures(
            restaurant_id=restaurant_id,
            suggestions_created=created,
            suggestions_read=read,
            suggestions_accepted=accepted,
            suggestions_dismissed=dismissed,
            suggestions_expired=expired,
            acceptance_rate=round(
                acceptance_rate,
                4,
            ),
            dismissal_rate=round(
                dismissal_rate,
                4,
            ),
            read_rate=round(
                read_rate,
                4,
            ),
            average_created_score=metrics[
                "average_created_score"
            ],
            average_accepted_score=metrics[
                "average_accepted_score"
            ],
            average_dismissed_score=metrics[
                "average_dismissed_score"
            ],
            average_expired_score=metrics[
                "average_expired_score"
            ],
            average_moves_accepted=metrics[
                "average_moves_accepted"
            ],
            average_seat_waste_accepted=metrics[
                "average_seat_waste_accepted"
            ],
            generated_at=datetime.now(
                timezone.utc,
            ),
        )