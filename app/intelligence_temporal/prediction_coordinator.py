from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
from app.models.table import Table

from .prediction import (
    ExpectedTurnRequest,
    ExpectedTurnService,
)
from .prediction_events import (
    TemporalPredictionEventService,
)
from .prediction_truth import (
    TemporalPredictionTruthService,
    TemporalTurnPredictionRecord,
)
from .snapshot import (
    TemporalLearningSnapshotService,
)


class TemporalTurnPredictionCoordinator:
    """
    Coordinates one auditable Expected Turn prediction for a
    persisted reservation.

    Transaction semantics:
    - no commit
    - no rollback
    - caller owns the transaction

    T3 semantics:
    - reads historical temporal truth
    - builds the current learning snapshot
    - predicts expected turn duration
    - records immutable prediction truth
    - persists the prediction event
    - does not calibrate
    - does not modify the reservation
    - does not modify the optimizer
    - does not invoke Brain or Autopilot
    """

    def __init__(
        self,
        *,
        snapshot_service: (
            TemporalLearningSnapshotService | None
        ) = None,
        event_service: (
            TemporalPredictionEventService | None
        ) = None,
    ) -> None:
        self.snapshot_service = (
            snapshot_service
            or TemporalLearningSnapshotService()
        )
        self.event_service = (
            event_service
            or TemporalPredictionEventService()
        )

    async def predict_for_reservation(
        self,
        *,
        session: AsyncSession,
        reservation: Reservation,
        predicted_at: datetime | None = None,
    ) -> TemporalTurnPredictionRecord:
        if reservation.restaurant_id is None:
            raise ValueError(
                "Temporal prediction requires restaurant_id."
            )

        if reservation.id is None:
            raise ValueError(
                "Temporal prediction requires a persisted "
                "reservation."
            )

        prediction_time = (
            predicted_at
            or datetime.now(timezone.utc)
        )

        service_area_id = await self._service_area_id(
            session=session,
            table_id=reservation.table_id,
        )

        snapshot = await self.snapshot_service.build(
            session=session,
            restaurant_id=reservation.restaurant_id,
        )

        prediction = ExpectedTurnService.predict(
            snapshot=snapshot,
            request=ExpectedTurnRequest(
                party_size=reservation.party_size,
                planned_duration_minutes=(
                    reservation.duration_minutes
                ),
                day_of_week=(
                    reservation.reservation_time.weekday()
                ),
                hour=reservation.reservation_time.hour,
                service_area_id=service_area_id,
            ),
        )

        record = TemporalPredictionTruthService.record(
            reservation_id=reservation.id,
            restaurant_id=reservation.restaurant_id,
            predicted_at=prediction_time,
            prediction=prediction,
        )

        await self.event_service.record_prediction(
            session=session,
            prediction=record,
        )

        return record

    @staticmethod
    async def _service_area_id(
        *,
        session: AsyncSession,
        table_id: UUID | None,
    ) -> UUID | None:
        if table_id is None:
            return None

        result = await session.execute(
            select(Table.service_area_id).where(
                Table.id == table_id
            )
        )

        return result.scalar_one_or_none()