from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.reservation import ReservationStatus
from app.schemas.reservation import ReservationUpdate
from app.services.reservation_service import (
    ReservationService,
)


class MutatingReservationRepository:
    """
    Mimics the important SQLAlchemy behavior for this test:
    update mutates and returns the same reservation object.
    """

    def __init__(self, reservation):
        self.db = SimpleNamespace()
        self.reservation = reservation

    async def update(
        self,
        reservation,
        updates,
    ):
        for key, value in updates.items():
            setattr(
                reservation,
                key,
                value,
            )

        return reservation


def _reservation(
    *,
    status: ReservationStatus,
):
    seated_at = datetime(
        2026,
        9,
        6,
        18,
        0,
        tzinfo=timezone.utc,
    )

    return SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        table_id=None,
        assigned_table_ids=[],
        customer_name="Temporal Guest",
        customer_phone="+15551234567",
        customer_email=None,
        party_size=2,
        reservation_time=datetime(
            2026,
            9,
            6,
            17,
            45,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        special_requests=None,
        status=status,
        seated_at=seated_at,
        completed_at=(
            datetime(
                2026,
                9,
                6,
                19,
                30,
                tzinfo=timezone.utc,
            )
            if status == ReservationStatus.COMPLETED
            else None
        ),
        cancelled_at=None,
        no_show_at=None,
        table_number=None,
    )


def _build_service(reservation):
    repository = MutatingReservationRepository(
        reservation
    )

    restaurant_repository = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=None
        ),
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=restaurant_repository,
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    service._record_reservation_event = AsyncMock()
    service._expire_pending_ai_suggestions = AsyncMock()
    service._try_record_temporal_outcome = AsyncMock()

    return service, repository


@pytest.mark.asyncio
async def test_system_update_records_outcome_on_completed_transition():
    reservation = _reservation(
        status=ReservationStatus.SEATED,
    )

    service, _ = _build_service(
        reservation
    )

    service.get_reservation = AsyncMock(
        return_value=reservation
    )

    updated = await service.update_reservation(
        reservation.id,
        ReservationUpdate(
            status=ReservationStatus.COMPLETED,
        ),
    )

    assert (
        updated.status
        == ReservationStatus.COMPLETED
    )

    assert updated.completed_at is not None

    service._try_record_temporal_outcome.assert_awaited_once_with(
        reservation=updated,
    )


@pytest.mark.asyncio
async def test_manager_update_records_outcome_on_completed_transition():
    reservation = _reservation(
        status=ReservationStatus.SEATED,
    )

    service, _ = _build_service(
        reservation
    )

    restaurant_ids = [
        reservation.restaurant_id
    ]

    service.get_reservation_for_restaurants = AsyncMock(
        return_value=reservation
    )

    updated = (
        await service
        .update_reservation_for_restaurants(
            reservation_id=reservation.id,
            restaurant_ids=restaurant_ids,
            payload=ReservationUpdate(
                status=ReservationStatus.COMPLETED,
            ),
        )
    )

    assert (
        updated.status
        == ReservationStatus.COMPLETED
    )

    assert updated.completed_at is not None

    service._try_record_temporal_outcome.assert_awaited_once_with(
        reservation=updated,
    )


@pytest.mark.asyncio
async def test_completed_to_completed_does_not_duplicate_outcome():
    reservation = _reservation(
        status=ReservationStatus.COMPLETED,
    )

    original_completed_at = (
        reservation.completed_at
    )

    service, _ = _build_service(
        reservation
    )

    service.get_reservation = AsyncMock(
        return_value=reservation
    )

    updated = await service.update_reservation(
        reservation.id,
        ReservationUpdate(
            status=ReservationStatus.COMPLETED,
        ),
    )

    assert (
        updated.status
        == ReservationStatus.COMPLETED
    )

    assert (
        updated.completed_at
        == original_completed_at
    )

    service._try_record_temporal_outcome.assert_not_awaited()