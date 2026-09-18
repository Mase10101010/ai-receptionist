from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.reservation import (
    Reservation,
    ReservationStatus,
)


class TemporalTurnObservation(BaseModel):
    reservation_id: UUID
    restaurant_id: UUID

    table_id: UUID | None
    service_area_id: UUID | None = None

    party_size: int

    reservation_time: datetime
    seated_at: datetime
    completed_at: datetime

    planned_duration_minutes: int
    actual_dining_minutes: int

    duration_delta_minutes: int


class TemporalObservationService:
    """
    Converts completed reservation lifecycle truth into temporal
    learning observations.

    T2 does not aggregate, predict, calibrate, or persist models here.
    Physical context such as service_area_id may be enriched by the
    database collection layer when available.
    """

    @staticmethod
    def from_reservation(
        reservation: Reservation,
    ) -> TemporalTurnObservation | None:
        if reservation.status != ReservationStatus.COMPLETED:
            return None

        if reservation.restaurant_id is None:
            return None

        if reservation.seated_at is None:
            return None

        if reservation.completed_at is None:
            return None

        elapsed = (
            reservation.completed_at
            - reservation.seated_at
        )

        actual_dining_minutes = int(
            elapsed.total_seconds() // 60
        )

        if actual_dining_minutes <= 0:
            return None

        return TemporalTurnObservation(
            reservation_id=reservation.id,
            restaurant_id=reservation.restaurant_id,
            table_id=reservation.table_id,
            service_area_id=None,
            party_size=reservation.party_size,
            reservation_time=reservation.reservation_time,
            seated_at=reservation.seated_at,
            completed_at=reservation.completed_at,
            planned_duration_minutes=(
                reservation.duration_minutes
            ),
            actual_dining_minutes=(
                actual_dining_minutes
            ),
            duration_delta_minutes=(
                actual_dining_minutes
                - reservation.duration_minutes
            ),
        )