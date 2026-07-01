import pytest

from app.providers.context import ProviderContext, ProviderDependencies
from app.providers.contract.refs import ProviderRef, ProviderType
from app.providers.contract.reservation import ReservationStatus
from app.providers.sevenrooms.provider import SevenRoomsProvider

from datetime import UTC, datetime

from app.providers.contract.availability import AvailabilityQuery, Channel, TimeRange

from datetime import timedelta

from app.providers.contract.availability import SlotToken
from app.providers.contract.guest import GuestInput
from app.providers.contract.refs import IdempotencyKey
from app.providers.contract.reservation import CreateReservationRequest



class FakeSevenRoomsClient:
    async def get_reservation(self, reservation_id: str) -> dict:
        return {
            "id": reservation_id,
            "status": "confirmed",
            "party_size": 2,
            "start": "2026-07-01T19:30:00Z",
            "duration_minutes": 90,
            "guest": {
                "full_name": "Test Guest",
                "email": "guest@example.com",
            },
        }


@pytest.mark.asyncio
async def test_get_reservation_returns_contract_reservation():
    provider = SevenRoomsProvider(
        context=ProviderContext(
            venue_id="venue-id",
            provider_type=ProviderType.SEVENROOMS,
            credentials={
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
            settings={
                "venue_id": "venue-id",
                "venue_group_id": "venue-group-id",
            },
        ),
        deps=ProviderDependencies(session=None),
        client = FakeSevenRoomsClient()
    )

    

    reservation = await provider.get_reservation(
        ProviderRef(
            provider=ProviderType.SEVENROOMS,
            external_id="sr-res-123",
        )
    )

    assert reservation is not None
    assert reservation.ref.provider == ProviderType.SEVENROOMS
    assert reservation.ref.external_id == "sr-res-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.party_size == 2
    assert reservation.guest.full_name == "Test Guest"
    assert reservation.guest.email == "guest@example.com"

class FakeSevenRoomsClientNotFound:
    async def get_reservation(self, reservation_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_get_reservation_returns_none_when_payload_not_found():
    provider = SevenRoomsProvider(
        context=ProviderContext(
            venue_id="venue-id",
            provider_type=ProviderType.SEVENROOMS,
            credentials={
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
            settings={
                "venue_id": "venue-id",
                "venue_group_id": "venue-group-id",
            },
        ),
        deps=ProviderDependencies(session=None),
        client = FakeSevenRoomsClientNotFound()
    )

    

    reservation = await provider.get_reservation(
        ProviderRef(
            provider=ProviderType.SEVENROOMS,
            external_id="missing-reservation",
        )
    )

    assert reservation is None

class FakeSevenRoomsAvailabilityClient:
    async def get_availability(self, payload: dict) -> dict:
        return {
            "slots": [
                {
                    "start": "2026-07-01T19:30:00Z",
                    "duration_minutes": 90,
                    "area": "Main Dining Room",
                    "party_size_max": 4,
                    "slot_token": "slot-token-123",
                    "is_request_only": False,
                }
            ]
        }


@pytest.mark.asyncio
async def test_get_availability_returns_contract_result():
    provider = SevenRoomsProvider(
        context=ProviderContext(
            venue_id="venue-id",
            provider_type=ProviderType.SEVENROOMS,
            credentials={
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
            settings={
                "venue_id": "venue-id",
                "venue_group_id": "venue-group-id",
            },
        ),
        deps=ProviderDependencies(session=None),
        client=FakeSevenRoomsAvailabilityClient(),
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
    assert result.slots[0].party_size_max == 4
    assert str(result.slots[0].slot_token) == "slot-token-123"

class FakeSevenRoomsCreateClient:
    async def create_reservation(self, payload: dict) -> dict:
        return {
            "id": "sr-created-123",
            "status": "confirmed",
            "party_size": payload["party_size"],
            "start": payload["start"],
            "duration_minutes": payload["duration_minutes"],
            "special_requests": payload["special_requests"],
            "guest": payload["guest"],
        }


@pytest.mark.asyncio
async def test_create_reservation_returns_contract_reservation():
    provider = SevenRoomsProvider(
        context=ProviderContext(
            venue_id="venue-id",
            provider_type=ProviderType.SEVENROOMS,
            credentials={
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
            settings={
                "venue_id": "venue-id",
                "venue_group_id": "venue-group-id",
            },
        ),
        deps=ProviderDependencies(session=None),
        client=FakeSevenRoomsCreateClient(),
    )

    reservation = await provider.create_reservation(
        CreateReservationRequest(
            venue_id="11111111-1111-1111-1111-111111111111",
            guest=GuestInput(
                full_name="Test Guest",
                phone="+61400000000",
                email="guest@example.com",
            ),
            party_size=2,
            start=datetime(2026, 7, 1, 19, 30, tzinfo=UTC),
            duration=timedelta(minutes=90),
            slot_token=SlotToken(value="slot-token-123"),
            special_requests="Window table if possible",
            tags=["vip"],
            channel=Channel.CONCIERGE_CHAT,
            client_token=IdempotencyKey(value="create-token-123"),
        )
    )

    assert reservation.ref.provider == ProviderType.SEVENROOMS
    assert reservation.ref.external_id == "sr-created-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.party_size == 2
    assert reservation.guest.full_name == "Test Guest"
    assert reservation.special_requests == "Window table if possible"