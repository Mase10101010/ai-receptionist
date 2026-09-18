from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import (
    Reservation,
    ReservationStatus,
)
from app.models.table import Table

from .observations import (
    TemporalObservationService,
    TemporalTurnObservation,
)


class TemporalObservationCollector:
    """
    Read-only SQLAlchemy collector for temporal learning truth.

    The collector:
    - reads completed reservations only
    - requires lifecycle timestamps
    - reuses TemporalObservationService for truth conversion
    - enriches observations with the primary table's service area
    - does not aggregate
    - does not predict
    - does not persist learned models
    - never commits
    """

    DEFAULT_LIMIT = 1000
    MAX_LIMIT = 5000

    async def collect(
        self,
        *,
        session: AsyncSession,
        restaurant_id: UUID,
        completed_since: datetime | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[TemporalTurnObservation]:
        if limit < 1:
            raise ValueError(
                "Temporal observation limit must be positive."
            )

        if limit > self.MAX_LIMIT:
            raise ValueError(
                f"Temporal observation limit cannot exceed "
                f"{self.MAX_LIMIT}."
            )

        statement = (
            select(
                Reservation,
                Table.service_area_id,
            )
            .outerjoin(
                Table,
                Table.id == Reservation.table_id,
            )
            .where(
                Reservation.restaurant_id
                == restaurant_id,
                Reservation.status
                == ReservationStatus.COMPLETED,
                Reservation.seated_at.is_not(None),
                Reservation.completed_at.is_not(None),
            )
            .order_by(
                Reservation.completed_at.desc(),
            )
            .limit(limit)
        )

        if completed_since is not None:
            statement = statement.where(
                Reservation.completed_at
                >= completed_since,
            )

        result = await session.execute(
            statement
        )

        observations: list[
            TemporalTurnObservation
        ] = []

        for (
            reservation,
            service_area_id,
        ) in result.all():
            observation = (
                TemporalObservationService
                .from_reservation(
                    reservation,
                )
            )

            if observation is None:
                continue

            if service_area_id is not None:
                observation = (
                    observation.model_copy(
                        update={
                            "service_area_id":
                                service_area_id,
                        },
                    )
                )

            observations.append(
                observation
            )

        return observations