import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.providers.native.provider
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User
from app.providers.contract.availability import AvailabilityQuery, Channel, TimeRange
from app.providers.contract.guest import GuestInput
from app.providers.contract.refs import IdempotencyKey, ProviderRef, ProviderType
from app.providers.contract.reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    ReservationChanges,
    ReservationStatus,
    UpdateReservationRequest,
)
from app.providers.resolver import (
    NullIntegrationConfigStore,
    ProviderResolver,
)


@pytest.mark.asyncio
async def test_alias_native_provider_full_flow(db_session):
    user = User(
        email=f"provider-smoke-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Provider Smoke Restaurant",
        slug=f"provider-smoke-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
    )
    db_session.add(restaurant)
    await db_session.flush()

    provider = await ProviderResolver(
        config_store=NullIntegrationConfigStore(),
    ).resolve(
        db_session,
        restaurant.id,
    )

    # Ensure an isolated service area and test table exist.
    service_area = ServiceArea(
        restaurant_id=restaurant.id,
        name=f"Provider Test {uuid.uuid4().hex[:8]}",
        area_type="indoor",
        is_active=True,
    )

    db_session.add(service_area)
    await db_session.flush()

    db_session.add(
        Table(
            restaurant_id=restaurant.id,
            service_area_id=service_area.id,
            table_code=f"TEST_AUTO_{uuid.uuid4().hex[:8]}",
            table_number=f"AUTO_{uuid.uuid4().hex[:8]}",
            seats=4,
            is_active=True,
        )
    )

    await db_session.commit()

    start = datetime.now(timezone.utc) + timedelta(days=5)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)

    availability = await provider.get_availability(
        AvailabilityQuery(
            venue_id=restaurant.id,
            party_size=2,
            window=TimeRange(
                start=start,
                end=start + timedelta(hours=2),
            ),
            channel=Channel.CONCIERGE_CHAT,
        )
    )

    assert len(availability.slots) >= 1

    created = await provider.create_reservation(
        CreateReservationRequest(
            venue_id=restaurant.id,
            guest=GuestInput(
                full_name="Pytest Native Provider",
                phone="+61000000002",
                email=None,
            ),
            party_size=2,
            start=start,
            duration=timedelta(minutes=90),
            special_requests="Created by provider pytest",
            tags=[],
            channel=Channel.CONCIERGE_CHAT,
            client_token=IdempotencyKey.generate(),
        )
    )

    await db_session.commit()

    assert created.status == ReservationStatus.CONFIRMED
    assert created.ref.provider == ProviderType.ALIAS_NATIVE

    fetched = await provider.get_reservation(
        ProviderRef(
            provider=ProviderType.ALIAS_NATIVE,
            external_id=created.ref.external_id,
        )
    )

    assert fetched is not None
    assert fetched.ref.external_id == created.ref.external_id

    updated = await provider.update_reservation(
        UpdateReservationRequest(
            ref=created.ref,
            changes=ReservationChanges(
                start=start + timedelta(hours=1),
                party_size=3,
                special_requests="Updated by provider pytest",
            ),
            client_token=IdempotencyKey.generate(),
        )
    )

    await db_session.commit()

    assert updated.party_size == 3
    assert updated.special_requests == "Updated by provider pytest"

    cancelled = await provider.cancel_reservation(
        CancelReservationRequest(
            ref=created.ref,
            reason="Provider pytest cleanup",
            client_token=IdempotencyKey.generate(),
        )
    )

    await db_session.commit()

    assert cancelled.status == ReservationStatus.CANCELLED
