from datetime import UTC, datetime

import pytest

from app.providers.context import ProviderContext, ProviderDependencies
from app.providers.contract.diagnostics import ProviderDiagnostics
from app.providers.contract.refs import ProviderType
from app.providers.thefork.provider import TheForkProvider
from app.providers.contract.availability import AvailabilityQuery, Channel, TimeRange

from datetime import timedelta

from app.providers.contract.guest import GuestInput
from app.providers.contract.refs import IdempotencyKey, ProviderRef
from app.providers.contract.reservation import (
    CreateReservationRequest,
    ReservationStatus,
    ReservationChanges,
    UpdateReservationRequest,
    CancelReservationRequest,
)


class FakeClient:
    async def health_check(self):
        return True

    async def diagnostics(self):
        return ProviderDiagnostics(
            provider=ProviderType.THEFORK,
            state="connected",
            checks=[],
        )
    
    async def get_availability(self, payload: dict):
        return {
            "slots": [
                {
                    "start": "2026-07-01T19:30:00Z",
                    "duration_minutes": 90,
                    "area": "Main Dining Room",
                    "party_size_max": 4,
                    "slot_token": "tf-slot-123",
                    "is_request_only": False,
                }
            ]
        }
    
    async def create_reservation(self, payload: dict):
        return {
            "id": "tf-created-123",
            "status": "confirmed",
            "party_size": payload["party_size"],
            "start": payload["start"],
            "duration_minutes": payload["duration_minutes"],
            "special_requests": payload["special_requests"],
            "guest": payload["guest"],
        }
    
    async def update_reservation(self, reservation_id: str, payload: dict):
        return {
            "id": reservation_id,
            "status": "confirmed",
            "party_size": payload["party_size"],
            "start": payload["start"],
            "duration_minutes": payload["duration_minutes"],
            "special_requests": payload["special_requests"],
            "tags": payload["tags"],
            "guest": {
                "full_name": "Updated Guest",
                "email": "updated@example.com",
            },
        }
    
    async def cancel_reservation(self, reservation_id: str, payload: dict):
        return {
            "id": reservation_id,
            "status": "cancelled",
            "party_size": 2,
            "start": "2026-07-01T19:30:00Z",
            "duration_minutes": 90,
            "special_requests": payload["reason"],
            "guest": {
                "full_name": "Cancelled Guest",
                "email": "cancelled@example.com",
            },
        }
    
    async def get_reservation(self, reservation_id: str):
        return {
            "id": reservation_id,
            "status": "confirmed",
            "party_size": 2,
            "start": "2026-07-01T19:30:00Z",
            "duration_minutes": 90,
            "guest": {
                "full_name": "Found Guest",
                "email": "found@example.com",
            },
        }
    
class FakeClientNotFound(FakeClient):
    async def get_reservation(self, reservation_id : str):
        return None 

@pytest.mark.asyncio
async def test_health_check():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="restaurant-1",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClient(),
    )

    health = await provider.health_check()

    assert health.healthy is True
    assert health.provider is ProviderType.THEFORK

@pytest.mark.asyncio
async def test_get_availability():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="11111111-1111-1111-1111-111111111111",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClient(),
    )

    result = await provider.get_availability(
        AvailabilityQuery(
            venue_id="11111111-1111-1111-1111-111111111111",
            party_size=2,
            window=TimeRange(
                start=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
                end=datetime(2026, 7, 1, 22, 0, tzinfo=UTC),
            ),
            channel=Channel.CONCIERGE_CHAT,
        )
    )

    assert len(result.slots) == 1
    assert result.slots[0].area == "Main Dining Room"
    assert str(result.slots[0].slot_token) == "tf-slot-123"

@pytest.mark.asyncio
async def test_create_reservation():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="11111111-1111-1111-1111-111111111111",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClient(),
    )

    reservation = await provider.create_reservation(
        CreateReservationRequest(
            venue_id="11111111-1111-1111-1111-111111111111",
            guest=GuestInput(
                full_name="Test Guest",
                email="guest@example.com",
            ),
            party_size=2,
            start=datetime(2026, 7, 1, 19, 30, tzinfo=UTC),
            duration=timedelta(minutes=90),
            special_requests="Window table",
            tags=["vip"],
            channel=Channel.CONCIERGE_CHAT,
            client_token=IdempotencyKey(value="tf-create-token"),
        )
    )

    assert reservation.ref.provider == ProviderType.THEFORK
    assert reservation.ref.external_id == "tf-created-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.guest.full_name == "Test Guest"

@pytest.mark.asyncio
async def test_update_reservation():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="11111111-1111-1111-1111-111111111111",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClient(),
    )

    reservation = await provider.update_reservation(
        UpdateReservationRequest(
            ref=ProviderRef(
                provider=ProviderType.THEFORK,
                external_id="tf-updated-123",
            ),
            changes=ReservationChanges(
                start=datetime(2026, 7, 1, 20, 0, tzinfo=UTC),
                party_size=3,
                duration=timedelta(minutes=120),
                special_requests="Updated request",
                tags=["vip", "updated"],
            ),
            client_token=IdempotencyKey(value="tf-update-token"),
        )
    )

    assert reservation.ref.provider == ProviderType.THEFORK
    assert reservation.ref.external_id == "tf-updated-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.party_size == 3
    assert reservation.guest.full_name == "Updated Guest"

@pytest.mark.asyncio
async def test_cancel_reservation():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="11111111-1111-1111-1111-111111111111",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClient(),
    )

    reservation = await provider.cancel_reservation(
        CancelReservationRequest(
            ref=ProviderRef(
                provider=ProviderType.THEFORK,
                external_id="tf-cancelled-123",
            ),
            reason="Guest requested cancellation",
            client_token=IdempotencyKey(value="tf-cancel-token"),
        )
    )

    assert reservation.ref.provider == ProviderType.THEFORK
    assert reservation.ref.external_id == "tf-cancelled-123"
    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.guest.full_name == "Cancelled Guest"
    assert reservation.special_requests == "Guest requested cancellation"

@pytest.mark.asyncio
async def test_get_reservation():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="11111111-1111-1111-1111-111111111111",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClient(),
    )

    reservation = await provider.get_reservation(
        ProviderRef(
            provider=ProviderType.THEFORK,
            external_id="tf-found-123",
        )
    )

    assert reservation is not None
    assert reservation.ref.provider == ProviderType.THEFORK
    assert reservation.ref.external_id == "tf-found-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.guest.full_name == "Found Guest"

@pytest.mark.asyncio
async def test_get_reservation_returns_none_when_not_found():
    provider = TheForkProvider(
        context=ProviderContext(
            venue_id="11111111-1111-1111-1111-111111111111",
            provider_type=ProviderType.THEFORK,
        ),
        deps=ProviderDependencies(session=None),
        client=FakeClientNotFound(),
    )

    reservation = await provider.get_reservation(
        ProviderRef(
            provider=ProviderType.THEFORK,
            external_id="tf-missing-123",
        )
    )

    assert reservation is None