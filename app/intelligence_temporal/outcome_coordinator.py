from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation

from .observations import (
    TemporalObservationService,
)
from .outcome_events import (
    TemporalPredictionOutcomeEventService,
)
from .prediction_reader import (
    TemporalPredictionEventReader,
)
from .prediction_truth import (
    TemporalPredictionTruthService,
    TemporalTurnPredictionOutcome,
)


class TemporalPredictionOutcomeCoordinator:
    """
    Coordinates prediction outcome truth for one completed
    reservation.

    Transaction semantics:
    - no commit
    - no rollback
    - caller owns the transaction

    T3 semantics:
    - reconstruct observed turn truth
    - retrieve original prediction truth
    - evaluate prediction error
    - persist immutable outcome event
    - no calibration
    - no Brain integration
    - no Autopilot integration
    """

    def __init__(
        self,
        *,
        prediction_reader: (
            TemporalPredictionEventReader | None
        ) = None,
        event_service: (
            TemporalPredictionOutcomeEventService | None
        ) = None,
    ) -> None:
        self.prediction_reader = (
            prediction_reader
            or TemporalPredictionEventReader()
        )

        self.event_service = (
            event_service
            or TemporalPredictionOutcomeEventService()
        )

    async def record_for_completed_reservation(
        self,
        *,
        session: AsyncSession,
        reservation: Reservation,
    ) -> TemporalTurnPredictionOutcome | None:
        if reservation.id is None:
            raise ValueError(
                "Temporal outcome requires "
                "a persisted reservation."
            )

        if reservation.restaurant_id is None:
            raise ValueError(
                "Temporal outcome requires restaurant_id."
            )

        observation = (
            TemporalObservationService
            .from_reservation(
                reservation
            )
        )

        if observation is None:
            return None

        prediction = (
            await self.prediction_reader
            .latest_for_reservation(
                session=session,
                restaurant_id=reservation.restaurant_id,
                reservation_id=reservation.id,
            )
        )

        if prediction is None:
            return None

        outcome = (
            TemporalPredictionTruthService
            .evaluate(
                prediction=prediction,
                observation=observation,
            )
        )

        await self.event_service.record_outcome(
            session=session,
            outcome=outcome,
        )

        return outcome