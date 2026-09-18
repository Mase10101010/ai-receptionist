from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import (
    Reservation,
    ReservationStatus,
)

from .live_turn import (
    LiveTurnPrediction,
    LiveTurnPredictionService,
)
from .prediction import ExpectedTurnPrediction
from .prediction_reader import (
    TemporalPredictionEventReader,
)


class LiveTurnCoordinator:
    """
    Read-only coordinator for live temporal intelligence.

    Pipeline:
        SEATED reservation
            +
        original persisted prediction
            ->
        live turn calculation

    Invariants:
    - only SEATED reservations are eligible
    - seated_at is required
    - original prediction truth is reused
    - no new prediction is generated
    - no event writes
    - no commit / rollback
    - invalid or missing prediction -> None
    - no Brain / optimizer / Autopilot integration
    """

    def __init__(
        self,
        *,
        prediction_reader: (
            TemporalPredictionEventReader | None
        ) = None,
    ) -> None:
        self.prediction_reader = (
            prediction_reader
            or TemporalPredictionEventReader()
        )

    async def calculate_for_reservation(
        self,
        *,
        session: AsyncSession,
        reservation: Reservation,
        evaluated_at: datetime,
    ) -> LiveTurnPrediction | None:
        if (
            reservation.status
            != ReservationStatus.SEATED
        ):
            return None

        if reservation.seated_at is None:
            return None

        if reservation.restaurant_id is None:
            return None

        prediction_record = await (
            self.prediction_reader
            .latest_for_reservation(
                session=session,
                restaurant_id=(
                    reservation.restaurant_id
                ),
                reservation_id=reservation.id,
            )
        )

        if prediction_record is None:
            return None

        prediction = ExpectedTurnPrediction(
            expected_duration_minutes=(
                prediction_record
                .expected_duration_minutes
            ),
            planned_duration_minutes=(
                prediction_record
                .planned_duration_minutes
            ),
            adjustment_minutes=(
                prediction_record
                .adjustment_minutes
            ),
            source=prediction_record.source,
            source_sample_count=(
                prediction_record
                .source_sample_count
            ),
            confidence=(
                prediction_record.confidence
            ),
            used_learned_pattern=(
                prediction_record
                .used_learned_pattern
            ),
        )

        return LiveTurnPredictionService.calculate(
            seated_at=reservation.seated_at,
            prediction=prediction,
            evaluated_at=evaluated_at,
        )