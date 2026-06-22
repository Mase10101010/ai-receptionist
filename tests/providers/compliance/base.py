import uuid
from datetime import datetime, timedelta, timezone

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


async def run_basic_provider_lifecycle_compliance(
    *,
    session,
    provider,
    restaurant_id: uuid.UUID,
    expected_provider_type: ProviderType,
) -> None:
    session.add(
        Table(
            restaurant_id=restaurant_id,
            table_code=f"COMPLIANCE_{uuid.uuid4().hex[:8]}",
            table_number=f"COMP_{uuid.uuid4().hex[:8]}",
            seats=4,
            is_active=True,
        )
    )
    await session.commit()

    start = datetime.now(timezone.utc) + timedelta(days=7)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)

    availability = await provider.get_availability(
        AvailabilityQuery(
            venue_id=restaurant_id,
            party_size=2,
            window=TimeRange(start=start, end=start + timedelta(hours=2)),
            channel=Channel.CONCIERGE_CHAT,
        )
    )

    assert len(availability.slots) >= 1

    created = await provider.create_reservation(
        CreateReservationRequest(
            venue_id=restaurant_id,
            guest=GuestInput(
                full_name="Reusable Compliance Test Guest",
                phone="+61000000004",
                email=None,
            ),
            party_size=2,
            start=start,
            duration=timedelta(minutes=90),
            special_requests="Created by reusable compliance test",
            tags=[],
            channel=Channel.CONCIERGE_CHAT,
            client_token=IdempotencyKey.generate(),
        )
    )
    await session.commit()

    assert created.status == ReservationStatus.CONFIRMED
    assert created.ref.provider == expected_provider_type

    fetched = await provider.get_reservation(
        ProviderRef(
            provider=expected_provider_type,
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
                special_requests="Updated by reusable compliance test",
            ),
            client_token=IdempotencyKey.generate(),
        )
    )
    await session.commit()

    assert updated.party_size == 3
    assert updated.special_requests == "Updated by reusable compliance test"

    cancelled = await provider.cancel_reservation(
        CancelReservationRequest(
            ref=created.ref,
            reason="Reusable compliance cleanup",
            client_token=IdempotencyKey.generate(),
        )
    )
    await session.commit()

    assert cancelled.status == ReservationStatus.CANCELLED