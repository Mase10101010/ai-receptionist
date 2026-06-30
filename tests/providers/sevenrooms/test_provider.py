import pytest

from app.providers.context import ProviderContext, ProviderDependencies
from app.providers.contract.refs import ProviderRef, ProviderType
from app.providers.contract.reservation import ReservationStatus
from app.providers.sevenrooms.provider import SevenRoomsProvider



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
    )

    provider._client = FakeSevenRoomsClient()

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
    )

    provider._client = FakeSevenRoomsClientNotFound()

    reservation = await provider.get_reservation(
        ProviderRef(
            provider=ProviderType.SEVENROOMS,
            external_id="missing-reservation",
        )
    )

    assert reservation is None