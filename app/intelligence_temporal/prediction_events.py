from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_events.service import (
    IntelligenceEventService,
)

from .prediction_truth import (
    TemporalTurnPredictionRecord,
)


class TemporalPredictionEventService:
    """
    Persists immutable temporal prediction truth into the existing
    Alias intelligence-event stream.

    Transaction semantics:
    - no commit
    - no rollback
    - caller owns the transaction

    T3 semantics:
    - prediction truth only
    - no calibration
    - no learning mutation
    - no Brain integration
    - no Autopilot integration
    """

    EVENT_SCHEMA = "temporal_turn_predicted.v1"

    async def record_prediction(
        self,
        *,
        session: AsyncSession,
        prediction: TemporalTurnPredictionRecord,
    ) -> IntelligenceEvent:
        event_service = IntelligenceEventService(
            IntelligenceEventRepository(
                session,
            )
        )

        return await event_service.record(
            restaurant_id=prediction.restaurant_id,
            event_type=(
                IntelligenceEventType
                .TEMPORAL_TURN_PREDICTED
            ),
            source=IntelligenceEventSource.SYSTEM,
            entity_type="reservation",
            entity_id=prediction.reservation_id,
            event_version=1,
            payload={
                "reservation_id": str(
                    prediction.reservation_id
                ),
                "predicted_at": (
                    prediction.predicted_at.isoformat()
                ),
                "expected_duration_minutes": (
                    prediction.expected_duration_minutes
                ),
                "planned_duration_minutes": (
                    prediction.planned_duration_minutes
                ),
                "adjustment_minutes": (
                    prediction.adjustment_minutes
                ),
                "source": prediction.source.value,
                "source_sample_count": (
                    prediction.source_sample_count
                ),
                "confidence": (
                    prediction.confidence.value
                ),
                "used_learned_pattern": (
                    prediction.used_learned_pattern
                ),
            },
            metadata={
                "service": (
                    "temporal_prediction_event_service"
                ),
                "event_schema": self.EVENT_SCHEMA,
            },
            occurred_at=prediction.predicted_at,
        )