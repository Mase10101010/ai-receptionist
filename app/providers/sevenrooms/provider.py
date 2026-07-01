from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..context import ProviderContext, ProviderDependencies
from ..contract.availability import AvailabilityQuery, AvailabilityResult
from ..contract.base import ProviderHealth, ReservationProvider
from ..contract.capabilities import ProviderCapabilities, SourceOfTruth
from ..contract.errors import ProviderValidationError
from ..contract.refs import ProviderRef, ProviderType
from ..contract.reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    Reservation,
    UpdateReservationRequest,
)
from ..registry import default_registry
from .client import SevenRoomsClient, SevenRoomsClientConfig
from ..contract.diagnostics import ProviderDiagnostics
from .mapper import to_availability_result, to_contract_reservation 
from collections.abc import Callable


_SEVENROOMS_CAPABILITIES = ProviderCapabilities(
    real_time_availability=True,
    create=True,
    modify=True,
    cancel=True,
    custom_duration=False,
    request_to_book=False,
    waitlist=False,
    deposits=False,
    guest_recognition=True,
    webhooks=True,
    idempotency_keys=False,
)


class SevenRoomsProvider:
    capabilities = _SEVENROOMS_CAPABILITIES
    source_of_truth = SourceOfTruth.EXTERNAL

    def __init__(
        self,
        context: ProviderContext,
        deps: ProviderDependencies,
        client: SevenRoomsClient | None = None,
        reservation_mapper: Callable[[dict], Reservation] = to_contract_reservation,
        availability_mapper: Callable[[dict], AvailabilityResult] = to_availability_result,
    ) -> None:
        self._context = context
        self._deps = deps
        self._reservation_mapper = reservation_mapper 
        self._availability_mapper = availability_mapper

        credentials = context.credentials or {}
        settings = context.settings or {}

        self._client = client or SevenRoomsClient(
            SevenRoomsClientConfig(
                client_id=credentials.get("client_id"),
                client_secret=credentials.get("client_secret"),
                venue_id=settings.get("venue_id") or credentials.get("venue_id"),
                venue_group_id=settings.get("venue_group_id")
                or credentials.get("venue_group_id"),
                base_url=settings.get("base_url", "https://api.sevenrooms.com"),
            )
        )
        
        self._mapper = to_contract_reservation

    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        payload = await self._client.get_availability(
            {
                "venue_id": str(query.venue_id),
                "party_size": query.party_size,
                "window_start": query.window.start.isoformat(),
                "window_end": query.window.end.isoformat(),
                "seating_preference": query.seating_preference,
                "channel": query.channel.value,
            }
        )

        return self._availability_mapper(payload)

    async def create_reservation(
        self,
        request: CreateReservationRequest,
    ) -> Reservation:
        payload = await self._client.create_reservation(
            {
                "venue_id": str(request.venue_id),
                "guest": {
                    "full_name": request.guest.full_name,
                    "phone": request.guest.phone,
                    "email": request.guest.email,
                    "notes": request.guest.notes,
                },
                "party_size": request.party_size,
                "start": request.start.isoformat(),
                "duration_minutes": int(request.duration.total_seconds() // 60)
                if request.duration
                else None,
                "slot_token": str(request.slot_token)
                if request.slot_token
                else None,
                "special_requests": request.special_requests,
                "tags": request.tags,
                "channel": request.channel.value,
                "client_token": str(request.client_token),
            }
        )

        return self._reservation_mapper(payload)

    async def update_reservation(
        self,
        request: UpdateReservationRequest,
    ) -> Reservation:
        raise NotImplementedError("SevenRooms update not implemented yet")

    async def cancel_reservation(
        self,
        request: CancelReservationRequest,
    ) -> Reservation:
        raise NotImplementedError("SevenRooms cancel not implemented yet")

    async def get_reservation(
        self,
        ref: ProviderRef,
    ) -> Reservation | None:
        payload = await self._client.get_reservation(ref.external_id)
        
        if payload is None:
            return None
        
        return self._reservation_mapper(payload)

    async def health_check(self) -> ProviderHealth:
        healthy = await self._client.health_check()

        return ProviderHealth(
            provider=ProviderType.SEVENROOMS,
            healthy=healthy,
            checked_at=datetime.now(UTC),
            detail="SevenRooms client configured" if healthy else "Missing SevenRooms API key",
        )
    
    async def diagnostics(self) -> ProviderDiagnostics:
        return await self._client.diagnostics()


def build_sevenrooms_provider(
    context: ProviderContext,
    deps: ProviderDependencies,
) -> SevenRoomsProvider:
    return SevenRoomsProvider(
        context=context,
        deps=deps,
    )


default_registry.register(
    ProviderType.SEVENROOMS,
    build_sevenrooms_provider,
)


if TYPE_CHECKING:
    _conforms: type[ReservationProvider] = SevenRoomsProvider