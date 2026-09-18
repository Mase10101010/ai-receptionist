from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db.session import AsyncSessionLocal
from app.intelligence_temporal.collector import (
    TemporalObservationCollector,
)
from app.models.reservation import (
    Reservation,
    ReservationStatus,
)
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User


@pytest.mark.asyncio
async def test_real_collector_reads_completed_turn_with_service_area():
    async with AsyncSessionLocal() as session:
        suffix = uuid4().hex

        try:
            user = User(
                email=f"temporal-{suffix}@example.com",
                hashed_password="test",
                full_name="Temporal Test",
                is_active=True,
                is_email_verified=True,
                subscription_status="trialing",
            )

            session.add(user)
            await session.flush()

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Temporal Restaurant {suffix[:8]}",
                slug=f"temporal-{suffix}",
                timezone="UTC",
                opening_hour=10,
                closing_hour=23,
                subscription_status="trialing",
            )

            session.add(restaurant)
            await session.flush()

            service_area = ServiceArea(
                restaurant_id=restaurant.id,
                name=f"Main Room {suffix[:8]}",
                area_type="indoor",
                is_active=True,
            )

            session.add(service_area)
            await session.flush()

            table = Table(
                restaurant_id=restaurant.id,
                service_area_id=service_area.id,
                table_code=f"TEMP_{suffix}",
                table_number=f"T-{suffix[:6]}",
                seats=4,
                is_active=True,
            )

            session.add(table)
            await session.flush()

            reservation_time = datetime(
                2026,
                9,
                3,
                18,
                0,
                tzinfo=timezone.utc,
            )

            seated_at = (
                reservation_time
                + timedelta(minutes=7)
            )

            completed_at = (
                seated_at
                + timedelta(minutes=74)
            )

            completed_reservation = Reservation(
                restaurant_id=restaurant.id,
                table_id=table.id,
                customer_name="Temporal Guest",
                customer_phone="+390000000000",
                customer_email=None,
                party_size=4,
                reservation_time=reservation_time,
                duration_minutes=90,
                status=ReservationStatus.COMPLETED,
                seated_at=seated_at,
                completed_at=completed_at,
            )

            session.add(completed_reservation)

            # This row must never become a temporal turn sample.
            seated_only_reservation = Reservation(
                restaurant_id=restaurant.id,
                table_id=table.id,
                customer_name="Still Dining",
                customer_phone="+390000000001",
                customer_email=None,
                party_size=2,
                reservation_time=(
                    reservation_time
                    + timedelta(hours=3)
                ),
                duration_minutes=90,
                status=ReservationStatus.SEATED,
                seated_at=(
                    seated_at
                    + timedelta(hours=3)
                ),
                completed_at=None,
            )

            session.add(seated_only_reservation)

            await session.flush()

            collector = (
                TemporalObservationCollector()
            )

            observations = await collector.collect(
                session=session,
                restaurant_id=restaurant.id,
            )

            assert len(observations) == 1

            observation = observations[0]

            assert (
                observation.reservation_id
                == completed_reservation.id
            )

            assert (
                observation.restaurant_id
                == restaurant.id
            )

            assert (
                observation.table_id
                == table.id
            )

            assert (
                observation.service_area_id
                == service_area.id
            )

            assert observation.party_size == 4

            assert (
                observation.reservation_time
                == reservation_time
            )

            assert (
                observation.seated_at
                == seated_at
            )

            assert (
                observation.completed_at
                == completed_at
            )

            assert (
                observation.planned_duration_minutes
                == 90
            )

            assert (
                observation.actual_dining_minutes
                == 74
            )

            assert (
                observation.duration_delta_minutes
                == -16
            )

        finally:
            await session.rollback()