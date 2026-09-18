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
    TemporalTurnPredictionOutcome,
)


class TemporalPredictionOutcomeEventService:
    """
    Persists immutable temporal prediction outcome truth into the
    existing Alias intelligence-event stream.

    Transaction semantics:
    - no commit
    - no rollback
    - caller owns the transaction

    T3 semantics:
    - prediction outcome truth only
    - no aggregation
    - no calibration
    - no confidence mutation
    - no Brain integration
    - no Autopilot integration
    """

    EVENT_SCHEMA = "temporal_turn_outcome_recorded.v1"

    async def record_outcome(
        self,
        *,
        session: AsyncSession,
        outcome: TemporalTurnPredictionOutcome,
    ) -> IntelligenceEvent:
        event_service = IntelligenceEventService(
            IntelligenceEventRepository(session)
        )

        return await event_service.record(
            restaurant_id=outcome.restaurant_id,
            event_type=(
                IntelligenceEventType
                .TEMPORAL_TURN_OUTCOME_RECORDED
            ),
            source=IntelligenceEventSource.SYSTEM,
            entity_type="reservation",
            entity_id=outcome.reservation_id,
            event_version=1,
            payload={
                "reservation_id": str(
                    outcome.reservation_id
                ),
                "predicted_at": (
                    outcome.predicted_at.isoformat()
                ),
                "predicted_duration_minutes": (
                    outcome.predicted_duration_minutes
                ),
                "actual_duration_minutes": (
                    outcome.actual_duration_minutes
                ),
                "signed_error_minutes": (
                    outcome.signed_error_minutes
                ),
                "absolute_error_minutes": (
                    outcome.absolute_error_minutes
                ),
                "source": outcome.source.value,
                "source_sample_count": (
                    outcome.source_sample_count
                ),
                "confidence": (
                    outcome.confidence.value
                ),
                "used_learned_pattern": (
                    outcome.used_learned_pattern
                ),
            },
            metadata={
                "service": (
                    "temporal_prediction_outcome_event_service"
                ),
                "event_schema": self.EVENT_SCHEMA,
            },
            occurred_at=outcome.completed_at,
        )