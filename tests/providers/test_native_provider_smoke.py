import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.providers.native.provider
from app.db.session import AsyncSessionLocal
from app.models.table import Table
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
from app.providers.resolver import ProviderResolver


RESTAURANT_ID = uuid.UUID("77488b28-620b-49f2-9148-d3539c9cf6d0")


@pytest.mark.asyncio
async def test_alias_native_provider_full_flow():
    session = AsyncSessionLocal()

    try:
        provider = await ProviderResolver().resolve(session, RESTAURANT_ID)

        # Ensure test tables exist
        session.add_all(
            [
                Table(
                    restaurant_id=RESTAURANT_ID,
                    table_code=f"TEST_AUTO_{uuid.uuid4().hex[:8]}",
                    table_number=f"AUTO_{uuid.uuid4().hex[:8]}",
                    seats=4,
                    is_active=True,
                ),
            ]
        )
        await session.commit()

        start = datetime.now(timezone.utc) + timedelta(days=5)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)

        availability = await provider.get_availability(
            AvailabilityQuery(
                venue_id=RESTAURANT_ID,
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
                venue_id=RESTAURANT_ID,
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

        await session.commit()

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

        await session.commit()

        assert updated.party_size == 3
        assert updated.special_requests == "Updated by provider pytest"

        cancelled = await provider.cancel_reservation(
            CancelReservationRequest(
                ref=created.ref,
                reason="Provider pytest cleanup",
                client_token=IdempotencyKey.generate(),
            )
        )

        await session.commit()

        assert cancelled.status == ReservationStatus.CANCELLED

    finally:
        await session.close()