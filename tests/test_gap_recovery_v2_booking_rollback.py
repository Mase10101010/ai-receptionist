"""PostgreSQL rollback test for missing reoptimization suggestions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import ConflictError
from app.db.session import AsyncSessionLocal
from app.intelligence_events.models import IntelligenceEvent
from app.models.reservation import Reservation
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.reservation import ReservationCreate
from app.services.ai_suggestion_service import AISuggestionService
from app.services.email_service import EmailService
from app.services.reservation_service import ReservationService


@pytest.mark.asyncio
async def test_missing_reoptimization_suggestion_rolls_back_booking_and_event():
    suffix = uuid4().hex
    user_id = None

    try:
        async with AsyncSessionLocal() as setup:
            user = User(
                email=f"gap-booking-rollback-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            setup.add(user)
            await setup.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Booking Rollback {suffix}",
                slug=f"gap-booking-rollback-{suffix}",
            )
            setup.add(restaurant)
            await setup.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            setup.add(area)
            await setup.flush()

            table = Table(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                table_code=f"GAP-{suffix}",
                table_number="1",
                seats=4,
            )
            setup.add(table)

            restaurant_id = restaurant.id
            await setup.commit()

        customer_name = f"Gap Rollback Guest {suffix}"

        async with AsyncSessionLocal() as session:
            service = ReservationService(
                repository=ReservationRepository(session),
                restaurant_repository=RestaurantRepository(session),
                table_repository=TableRepository(session),
                email_service=EmailService(),
            )

            service._validate_reservation_time = AsyncMock()
            service._assign_tables_with_aie = AsyncMock(
                return_value=(None, []),
            )
            service._reoptimization_available = AsyncMock(
                return_value=True,
            )
            service._try_record_temporal_prediction = AsyncMock()

            payload = ReservationCreate(
                restaurant_id=restaurant_id,
                customer_name=customer_name,
                customer_phone="+15551234567",
                party_size=4,
                reservation_time=(
                    datetime.now(timezone.utc)
                    + timedelta(days=10)
                ),
                duration_minutes=90,
            )

            with patch.object(
                AISuggestionService,
                "analyze_reservation",
                new=AsyncMock(return_value=None),
            ):
                with pytest.raises(
                    ConflictError,
                    match="reoptimization",
                ):
                    await service.create_reservation(payload)

            # Explicitly reproduce get_db's exception rollback.
            await session.rollback()

        async with AsyncSessionLocal() as verification:
            reservations = (
                await verification.execute(
                    select(Reservation).where(
                        Reservation.restaurant_id == restaurant_id,
                        Reservation.customer_name == customer_name,
                    )
                )
            ).scalars().all()

            events = (
                await verification.execute(
                    select(IntelligenceEvent).where(
                        IntelligenceEvent.restaurant_id == restaurant_id,
                    )
                )
            ).scalars().all()

            assert reservations == []
            assert events == []

    finally:
        if user_id is not None:
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(
                    delete(User).where(User.id == user_id)
                )
                await cleanup.commit()
