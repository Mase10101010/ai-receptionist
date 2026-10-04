from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import ValidationError
from app.db.session import AsyncSessionLocal
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)
from app.models.reservation import (
    Reservation,
    ReservationStatus,
)
from app.models.reservation_table_assignment import (
    ReservationTableAssignment,
)
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User
from app.repositories.table_repository import TableRepository


@pytest.mark.asyncio
async def test_postgresql_apply_reoptimization_rechecks_live_occupancy_after_table_lock():
    setup_session = AsyncSessionLocal()

    user_id = None
    restaurant_id = None
    table_id = None
    seated_reservation_id = None
    target_reservation_id = None

    try:
        suffix = uuid4().hex

        user = User(
            email=f"lab011-{suffix}@example.com",
            hashed_password="test",
            is_active=True,
            is_email_verified=True,
        )
        setup_session.add(user)
        await setup_session.flush()
        user_id = user.id

        restaurant = Restaurant(
            owner_id=user.id,
            name=f"LAB011 PostgreSQL {suffix}",
            slug=f"lab011-postgresql-{suffix}",
        )
        setup_session.add(restaurant)
        await setup_session.flush()
        restaurant_id = restaurant.id

        service_area = ServiceArea(
            restaurant_id=restaurant.id,
            name=f"LAB011 Area {suffix}",
        )
        setup_session.add(service_area)
        await setup_session.flush()

        table = Table(
            restaurant_id=restaurant.id,
            service_area_id=service_area.id,
            table_code=f"LAB011-{suffix}",
            table_number=f"LAB011-{suffix}",
            seats=2,
        )
        setup_session.add(table)
        await setup_session.flush()
        table_id = table.id

        first_start = (
            datetime.now(timezone.utc)
            + timedelta(days=10)
        )
        target_start = first_start + timedelta(minutes=90)

        live_reservation = Reservation(
            restaurant_id=restaurant.id,
            table_id=table.id,
            customer_name="LAB011 Live Guest",
            customer_phone="+15550000101",
            party_size=2,
            reservation_time=first_start,
            duration_minutes=90,
            status=ReservationStatus.CONFIRMED,
        )

        target_reservation = Reservation(
            restaurant_id=restaurant.id,
            table_id=table.id,
            customer_name="LAB011 Target Guest",
            customer_phone="+15550000102",
            party_size=2,
            reservation_time=target_start,
            duration_minutes=90,
            status=ReservationStatus.CONFIRMED,
        )

        setup_session.add_all(
            [
                live_reservation,
                target_reservation,
            ]
        )
        await setup_session.flush()

        seated_reservation_id = live_reservation.id
        target_reservation_id = target_reservation.id

        setup_session.add_all(
            [
                ReservationTableAssignment(
                    reservation_id=live_reservation.id,
                    table_id=table.id,
                    is_primary=True,
                ),
                ReservationTableAssignment(
                    reservation_id=target_reservation.id,
                    table_id=table.id,
                    is_primary=True,
                ),
            ]
        )

        await setup_session.commit()

        # Two genuinely independent PostgreSQL transactions.
        first_session = AsyncSessionLocal()
        apply_session = AsyncSessionLocal()

        try:
            # Transaction A owns the physical-table lock first.
            #
            # The Apply transaction must eventually wait on exactly
            # this row before it can revalidate authoritative live
            # occupancy.
            await TableRepository(
                first_session,
            ).lock_by_ids(
                [table_id],
            )

            intelligence_service = (
                IntelligenceOptimizationService()
            )

            async def apply_stale_plan():
                try:
                    await intelligence_service.apply_reoptimization(
                        session=apply_session,
                        payload=(
                            IntelligenceApplyReoptimizationRequest(
                                new_reservation_id=(
                                    target_reservation_id
                                ),
                                new_reservation_table_ids=[
                                    table_id,
                                ],
                                new_reservation_primary_table_id=(
                                    table_id
                                ),
                                moves=[],
                            )
                        ),
                        allowed_restaurant_ids=[
                            restaurant_id,
                        ],
                    )

                    await apply_session.commit()
                    return "applied"

                except ValidationError:
                    await apply_session.rollback()
                    return "rejected"

            apply_task = asyncio.create_task(
                apply_stale_plan()
            )

            # Apply may perform its preliminary reads, but it must
            # eventually block when it reaches the destination-table
            # SELECT ... FOR UPDATE owned by transaction A.
            await asyncio.sleep(0.2)

            assert not apply_task.done(), (
                "Reoptimization Apply did not wait for the "
                "physical-table PostgreSQL row lock."
            )

            # While still owning the same physical-table lock,
            # transaction A changes the authoritative live state.
            live_result = await first_session.execute(
                select(Reservation).where(
                    Reservation.id
                    == seated_reservation_id,
                )
            )

            live_in_first_transaction = (
                live_result.scalar_one()
            )

            live_in_first_transaction.status = (
                ReservationStatus.SEATED
            )
            live_in_first_transaction.seated_at = (
                datetime.now(timezone.utc)
            )

            await first_session.flush()
            await first_session.commit()

            # Apply can now acquire the table lock. Its live occupancy
            # query must execute after that acquisition and observe the
            # newly committed SEATED reservation.
            apply_result = await asyncio.wait_for(
                apply_task,
                timeout=5,
            )

            assert apply_result == "rejected"

        finally:
            await first_session.rollback()
            await first_session.close()

            await apply_session.rollback()
            await apply_session.close()

        # Verify fail-closed persistence after both transactions.
        verification_session = AsyncSessionLocal()

        try:
            result = await verification_session.execute(
                select(Reservation).where(
                    Reservation.id.in_(
                        [
                            seated_reservation_id,
                            target_reservation_id,
                        ]
                    )
                )
            )

            reservations = {
                reservation.id: reservation
                for reservation in result.scalars().all()
            }

            assert (
                reservations[seated_reservation_id].status
                == ReservationStatus.SEATED
            )

            assert (
                reservations[target_reservation_id].status
                == ReservationStatus.CONFIRMED
            )

            assert (
                reservations[target_reservation_id].table_id
                == table_id
            )

            assignment_result = (
                await verification_session.execute(
                    select(
                        ReservationTableAssignment,
                    ).where(
                        ReservationTableAssignment.reservation_id
                        == target_reservation_id,
                    )
                )
            )

            target_assignments = list(
                assignment_result.scalars().all()
            )

            assert len(target_assignments) == 1
            assert (
                target_assignments[0].table_id
                == table_id
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
                    delete(User).where(
                        User.id == user_id
                    )
                )
                await cleanup_session.commit()
            finally:
                await cleanup_session.close()