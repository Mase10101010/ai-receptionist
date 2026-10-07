import uuid
from datetime import datetime, timezone

import pytest

from app.models.ai_suggestion import (
    AISuggestion,
    AISuggestionStatus,
    AISuggestionType,
)
from app.models.reservation import Reservation, ReservationStatus
from app.models.restaurant import Restaurant
from app.models.user import User
from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)


@pytest.mark.asyncio
async def test_find_pending_for_reservation_filters_by_suggestion_type(
    db_session,
):
    user = User(
        email=f"lab012-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="LAB-012 Suggestion Restaurant",
        slug=f"lab012-suggestion-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(restaurant)
    await db_session.flush()

    reservation = Reservation(
        restaurant_id=restaurant.id,
        customer_name="LAB-012 Guest",
        customer_phone="000000000",
        customer_email="lab012@example.com",
        party_size=2,
        reservation_time=datetime(
            2026,
            10,
            17,
            19,
            30,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
    )
    db_session.add(reservation)
    await db_session.flush()

    reoptimization = AISuggestion(
        restaurant_id=restaurant.id,
        reservation_id=reservation.id,
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        status=AISuggestionStatus.PENDING,
        title="Reoptimization",
        description="Existing reoptimization lane",
        payload={},
    )

    live_modification = AISuggestion(
        restaurant_id=restaurant.id,
        reservation_id=reservation.id,
        suggestion_type=(
            AISuggestionType.LIVE_SEATED_MODIFICATION
        ),
        status=AISuggestionStatus.PENDING,
        title="Live seated modification",
        description="Dedicated live-service lane",
        payload={},
    )

    db_session.add_all(
        [
            reoptimization,
            live_modification,
        ]
    )
    await db_session.flush()

    repository = AISuggestionRepository(db_session)

    found_reoptimization = (
        await repository.find_pending_for_reservation(
            reservation.id,
            suggestion_type=AISuggestionType.REOPTIMIZATION,
        )
    )

    found_live_modification = (
        await repository.find_pending_for_reservation(
            reservation.id,
            suggestion_type=(
                AISuggestionType.LIVE_SEATED_MODIFICATION
            ),
        )
    )

    assert found_reoptimization is not None
    assert found_reoptimization.id == reoptimization.id
    assert (
        found_reoptimization.suggestion_type
        == AISuggestionType.REOPTIMIZATION
    )

    assert found_live_modification is not None
    assert found_live_modification.id == live_modification.id
    assert (
        found_live_modification.suggestion_type
        == AISuggestionType.LIVE_SEATED_MODIFICATION
    )



@pytest.mark.asyncio
async def test_expire_pending_for_reservation_filters_by_suggestion_type(
    db_session,
):
    user = User(
        email=f"lab012-expire-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="LAB-012 Expiration Restaurant",
        slug=f"lab012-expire-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(restaurant)
    await db_session.flush()

    reservation = Reservation(
        restaurant_id=restaurant.id,
        customer_name="LAB-012 Expiration Guest",
        customer_phone="000000000",
        customer_email="lab012-expire@example.com",
        party_size=2,
        reservation_time=datetime(
            2026,
            10,
            17,
            19,
            30,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
    )
    db_session.add(reservation)
    await db_session.flush()

    reoptimization = AISuggestion(
        restaurant_id=restaurant.id,
        reservation_id=reservation.id,
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        status=AISuggestionStatus.PENDING,
        title="Reoptimization",
        description="Must remain pending",
        payload={},
    )

    live_modification = AISuggestion(
        restaurant_id=restaurant.id,
        reservation_id=reservation.id,
        suggestion_type=(
            AISuggestionType.LIVE_SEATED_MODIFICATION
        ),
        status=AISuggestionStatus.PENDING,
        title="Live seated modification",
        description="Must expire",
        payload={},
    )

    db_session.add_all(
        [reoptimization, live_modification]
    )
    await db_session.flush()

    repository = AISuggestionRepository(db_session)

    expired = (
        await repository.expire_pending_for_reservation(
            reservation.id,
            suggestion_type=(
                AISuggestionType.LIVE_SEATED_MODIFICATION
            ),
        )
    )

    assert [item.id for item in expired] == [
        live_modification.id
    ]

    assert (
        live_modification.status
        == AISuggestionStatus.EXPIRED
    )
    assert (
        reoptimization.status
        == AISuggestionStatus.PENDING
    )
