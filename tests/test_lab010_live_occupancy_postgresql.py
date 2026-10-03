from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import ConflictError
from app.db.session import AsyncSessionLocal
from app.models.reservation import Reservation, ReservationStatus
from app.models.reservation_table_assignment import ReservationTableAssignment
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.reservation import ReservationUpdate
from app.services.email_service import EmailService
from app.services.reservation_service import ReservationService


def _build_reservation_service(session):
    return ReservationService(
        repository=ReservationRepository(session),
        restaurant_repository=RestaurantRepository(session),
        table_repository=TableRepository(session),
        email_service=EmailService(),
    )


@pytest.mark.asyncio
async def test_postgresql_serializes_concurrent_seating_on_same_physical_table():
    setup_session = AsyncSessionLocal()

    user_id = None
    restaurant_id = None
    table_id = None
    first_reservation_id = None
    second_reservation_id = None

    try:
        suffix = uuid4().hex

        user = User(
            email=f"lab010-{suffix}@example.com",
            hashed_password="test",
            is_active=True,
            is_email_verified=True,
        )
        setup_session.add(user)
        await setup_session.flush()
        user_id = user.id

        restaurant = Restaurant(
            owner_id=user.id,
            name=f"LAB010 PostgreSQL {suffix}",
            slug=f"lab010-postgresql-{suffix}",
        )
        setup_session.add(restaurant)
        await setup_session.flush()
        restaurant_id = restaurant.id

        service_area = ServiceArea(
            restaurant_id=restaurant.id,
            name=f"LAB010 Area {suffix}",
        )
        setup_session.add(service_area)
        await setup_session.flush()

        table = Table(
            restaurant_id=restaurant.id,
            service_area_id=service_area.id,
            table_code=f"LAB010-{suffix}",
            table_number=f"LAB010-{suffix}",
            seats=2,
        )
        setup_session.add(table)
        await setup_session.flush()
        table_id = table.id

        reservation_time = datetime.now(timezone.utc) + timedelta(days=10)

        first_reservation = Reservation(
            restaurant_id=restaurant.id,
            table_id=table.id,
            customer_name="LAB010 Concurrent Guest A",
            customer_phone="+15550000001",
            party_size=2,
            reservation_time=reservation_time,
            duration_minutes=90,
            status=ReservationStatus.CONFIRMED,
        )

        second_reservation = Reservation(
            restaurant_id=restaurant.id,
            table_id=table.id,
            customer_name="LAB010 Concurrent Guest B",
            customer_phone="+15550000002",
            party_size=2,
            reservation_time=reservation_time + timedelta(minutes=90),
            duration_minutes=90,
            status=ReservationStatus.CONFIRMED,
        )

        setup_session.add_all(
            [
                first_reservation,
                second_reservation,
            ]
        )
        await setup_session.flush()

        first_reservation_id = first_reservation.id
        second_reservation_id = second_reservation.id

        setup_session.add_all(
            [
                ReservationTableAssignment(
                    reservation_id=first_reservation.id,
                    table_id=table.id,
                    is_primary=True,
                ),
                ReservationTableAssignment(
                    reservation_id=second_reservation.id,
                    table_id=table.id,
                    is_primary=True,
                ),
            ]
        )

        await setup_session.commit()

        # Two genuinely independent PostgreSQL transactions.
        first_session = AsyncSessionLocal()
        second_session = AsyncSessionLocal()

        try:
            first_service = _build_reservation_service(first_session)
            second_service = _build_reservation_service(second_session)

            first_table_repository = TableRepository(first_session)

            # Transaction A deliberately acquires the physical-table row lock
            # and keeps it open. This gives us deterministic contention rather
            # than relying on task scheduling luck.
            await first_table_repository.lock_by_ids([table_id])

            async def seat_second_reservation():
                try:
                    await second_service.update_reservation_for_restaurants(
                        reservation_id=second_reservation_id,
                        restaurant_ids=[restaurant_id],
                        payload=ReservationUpdate(
                            status=ReservationStatus.SEATED,
                        ),
                    )
                    await second_session.commit()
                    return "seated"
                except ConflictError:
                    await second_session.rollback()
                    return "conflict"

            second_task = asyncio.create_task(
                seat_second_reservation()
            )

            # Give transaction B a chance to reach SELECT ... FOR UPDATE.
            # Because transaction A owns the physical-table lock, B must not
            # be able to finish yet.
            await asyncio.sleep(0.2)

            assert not second_task.done(), (
                "The competing seating transaction did not wait for the "
                "physical-table PostgreSQL row lock."
            )

            # Transaction A seats its reservation while still owning the same
            # physical-table lock, then commits and releases it.
            await first_service.update_reservation_for_restaurants(
                reservation_id=first_reservation_id,
                restaurant_ids=[restaurant_id],
                payload=ReservationUpdate(
                    status=ReservationStatus.SEATED,
                ),
            )
            await first_session.commit()

            # Transaction B may now acquire the lock. It must re-check live
            # occupancy and reject its own seating transition.
            second_result = await asyncio.wait_for(
                second_task,
                timeout=5,
            )

            assert second_result == "conflict"

        finally:
            await first_session.rollback()
            await first_session.close()

            await second_session.rollback()
            await second_session.close()

        verification_session = AsyncSessionLocal()

        try:
            result = await verification_session.execute(
                select(Reservation).where(
                    Reservation.id.in_(
                        [
                            first_reservation_id,
                            second_reservation_id,
                        ]
                    )
                )
            )

            reservations = {
                reservation.id: reservation
                for reservation in result.scalars().all()
            }

            assert (
                reservations[first_reservation_id].status
                == ReservationStatus.SEATED
            )
            assert (
                reservations[first_reservation_id].seated_at
                is not None
            )

            assert (
                reservations[second_reservation_id].status
                == ReservationStatus.CONFIRMED
            )
            assert (
                reservations[second_reservation_id].seated_at
                is None
            )

        finally:
            await verification_session.close()

    finally:
        await setup_session.rollback()
        await setup_session.close()

        if user_id is not None:
            cleanup_session = AsyncSessionLocal()

            try:
                await cleanup_session.execute(
                    delete(User).where(User.id == user_id)
                )
                await cleanup_session.commit()
            finally:
                await cleanup_session.close()