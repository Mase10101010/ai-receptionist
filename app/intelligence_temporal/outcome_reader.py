from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEvent,
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
    TemporalTurnPredictionOutcome,
)


class TemporalOutcomeEventReader:
    """
    Read-only access to persisted temporal prediction outcomes.

    T4.1 responsibilities only:
    - retrieve TEMPORAL_TURN_OUTCOME_RECORDED events
    - reconstruct typed TemporalTurnPredictionOutcome records
    - optionally filter by completion-time range
    - tolerate malformed historical events

    No aggregation.
    No calibration.
    No persistence.
    No transaction mutation.
    """

    DEFAULT_LIMIT = 1000
    MAX_LIMIT = 5000

    async def list_for_restaurant(
        self,
        *,
        session: AsyncSession,
        restaurant_id: UUID,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[TemporalTurnPredictionOutcome]:
        safe_limit = max(
            1,
            min(
                limit,
                self.MAX_LIMIT,
            ),
        )

        safe_offset = max(
            0,
            offset,
        )

        repository = IntelligenceEventRepository(
            session,
        )

        events = await repository.list_for_restaurant(
            restaurant_id=restaurant_id,
            limit=safe_limit,
            offset=safe_offset,
            event_type=(
                IntelligenceEventType
                .TEMPORAL_TURN_OUTCOME_RECORDED
            ),
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )

        outcomes: list[
            TemporalTurnPredictionOutcome
        ] = []

        for event in events:
            outcome = self._from_event(
                event=event,
                restaurant_id=restaurant_id,
            )

            if outcome is not None:
                outcomes.append(outcome)

        return outcomes

    @staticmethod
    def _from_event(
        *,
        event: IntelligenceEvent,
        restaurant_id: UUID,
    ) -> TemporalTurnPredictionOutcome | None:
        if event.restaurant_id != restaurant_id:
            return None

        if (
            event.event_type
            != IntelligenceEventType
            .TEMPORAL_TURN_OUTCOME_RECORDED
        ):
            return None

        if event.entity_type != "reservation":
            return None

        if event.entity_id is None:
            return None

        payload = event.payload

        if not isinstance(payload, dict):
            return None

        try:
            payload_reservation_id = UUID(
                str(
                    payload["reservation_id"],
                )
            )

            if (
                payload_reservation_id
                != event.entity_id
            ):
                return None

            predicted_at = datetime.fromisoformat(
                str(
                    payload["predicted_at"],
                )
            )

            return TemporalTurnPredictionOutcome(
                reservation_id=payload_reservation_id,
                restaurant_id=restaurant_id,
                predicted_at=predicted_at,
                completed_at=event.occurred_at,
                predicted_duration_minutes=int(
                    payload[
                        "predicted_duration_minutes"
                    ]
                ),
                actual_duration_minutes=int(
                    payload[
                        "actual_duration_minutes"
                    ]
                ),
                signed_error_minutes=int(
                    payload[
                        "signed_error_minutes"
                    ]
                ),
                absolute_error_minutes=int(
                    payload[
                        "absolute_error_minutes"
                    ]
                ),
                source=ExpectedTurnSource(
                    payload["source"]
                ),
                source_sample_count=(
                    int(
                        payload[
                            "source_sample_count"
                        ]
                    )
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