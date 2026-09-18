from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)

from .prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from .prediction_truth import (
    TemporalTurnPredictionRecord,
)


class TemporalPredictionEventReader:
    """
    Reconstructs immutable temporal prediction truth from the
    existing Alias intelligence-event stream.

    T3 semantics:
    - read-only
    - no calibration
    - no learning mutation
    - no reservation mutation
    - no Brain integration
    - no Autopilot integration

    Invalid or missing historical prediction truth fails closed
    by returning None.
    """

    async def latest_for_reservation(
        self,
        *,
        session: AsyncSession,
        restaurant_id: UUID,
        reservation_id: UUID,
    ) -> TemporalTurnPredictionRecord | None:
        repository = IntelligenceEventRepository(session)

        events = await repository.list_for_restaurant(
            restaurant_id=restaurant_id,
            limit=1,
            event_type=(
                IntelligenceEventType
                .TEMPORAL_TURN_PREDICTED
            ),
            entity_type="reservation",
            entity_id=reservation_id,
        )

        if not events:
            return None

        event = events[0]
        payload = event.payload

        if not isinstance(payload, dict):
            return None

        try:
            payload_reservation_id = UUID(
                str(payload["reservation_id"])
            )

            if payload_reservation_id != reservation_id:
                return None

            predicted_at = datetime.fromisoformat(
                str(payload["predicted_at"])
            )

            return TemporalTurnPredictionRecord(
                reservation_id=payload_reservation_id,
                restaurant_id=restaurant_id,
                predicted_at=predicted_at,
                expected_duration_minutes=int(
                    payload[
                        "expected_duration_minutes"
                    ]
                ),
                planned_duration_minutes=int(
                    payload[
                        "planned_duration_minutes"
                    ]
                ),
                adjustment_minutes=int(
                    payload["adjustment_minutes"]
                ),
                source=ExpectedTurnSource(
                    payload["source"]
                ),
                source_sample_count=(
                    int(payload["source_sample_count"])
                    if payload.get(
                        "source_sample_count"
                    )
                    is not None
                    else None
                ),
                confidence=ExpectedTurnConfidence(
                    payload["confidence"]
                ),
                used_learned_pattern=bool(
                    payload[
                        "used_learned_pattern"
                    ]
                ),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return None