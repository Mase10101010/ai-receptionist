from datetime import UTC, datetime
from typing import TYPE_CHECKING
from collections.abc import Callable

from ..context import ProviderContext, ProviderDependencies
from ..contract.availability import AvailabilityQuery, AvailabilityResult
from ..contract.base import ProviderHealth, ReservationProvider
from ..contract.capabilities import ProviderCapabilities, SourceOfTruth
from ..contract.diagnostics import ProviderDiagnostics
from ..contract.refs import ProviderRef, ProviderType
from ..contract.reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    Reservation,
    UpdateReservationRequest,
)
from ..registry import default_registry
from .client import TheForkClient, TheForkClientConfig
from .mapper import to_availability_result, to_contract_reservation


_THEFORK_CAPABILITIES = ProviderCapabilities(
    real_time_availability=True,
    create=True,
    modify=True,
    cancel=True,
    custom_duration=False,
    request_to_book=False,
    waitlist=False,
    deposits=False,
    guest_recognition=False,
    webhooks=True,
    idempotency_keys=True,
)


class TheForkProvider:
    provider_type = ProviderType.THEFORK
    capabilities = _THEFORK_CAPABILITIES
    source_of_truth = SourceOfTruth.EXTERNAL

    def __init__(
        self,
        context: ProviderContext,
        deps: ProviderDependencies,
        client: TheForkClient | None = None,
        reservation_mapper: Callable[[dict], Reservation] = to_contract_reservation,
        availability_mapper: Callable[[dict], AvailabilityResult] = to_availability_result,
    ) -> None:
        self._context = context
        self._deps = deps
        self._reservation_mapper = reservation_mapper
        self._availability_mapper = availability_mapper

        credentials = context.credentials or {}
        settings = context.settings or {}

        self._client = client or TheForkClient(
            TheForkClientConfig(
                client_id=credentials.get("client_id"),
                client_secret=credentials.get("client_secret"),
                restaurant_id=settings.get("restaurant_id")
                or credentials.get("restaurant_id"),
                base_url=settings.get("base_url", "https://api.thefork.com"),
            )
        )

    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        payload = await self._client.get_availability(
            {
                "restaurant_id": str(query.venue_id),
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
                "restaurant_id": str(request.venue_id),
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
        changes = request.changes

        payload = await self._client.update_reservation(
            request.ref.external_id,
            {
                "start": changes.start.isoformat()
                if changes.start
                else None,
                "party_size": changes.party_size,
                "duration_minutes": int(changes.duration.total_seconds() // 60)
                if changes.duration
                else None,
                "special_requests": changes.special_requests,
                "tags": changes.tags,
                "slot_token": str(changes.slot_token)
                if changes.slot_token
                else None,
                "client_token": str(request.client_token),
            },
        )

        return self._reservation_mapper(payload)
    
    async def cancel_reservation(
        self,
        request: CancelReservationRequest,
    ) -> Reservation:
        payload = await self._client.cancel_reservation(
            request.ref.external_id,
            {
                "reason": request.reason,
                "client_token": str(request.client_token),
            },
        )

        return self._reservation_mapper(payload)
    
    async def get_reservation(
        self,
        ref: ProviderRef,
    ) -> Reservation | None:
        payload = await self._client.get_reservation(
            ref.external_id,
        )

        if payload is None:
            return None

        return self._reservation_mapper(payload)

    async def health_check(self) -> ProviderHealth:
        healthy = await self._client.health_check()

        return ProviderHealth(
            provider=ProviderType.THEFORK,
            healthy=healthy,
            checked_at=datetime.now(UTC),
            detail="TheFork client configured" if healthy else "Missing TheFork credentials",
        )

    async def diagnostics(self) -> ProviderDiagnostics:
        return await self._client.diagnostics()


def build_thefork_provider(
    context: ProviderContext,
    deps: ProviderDependencies,
) -> TheForkProvider:
    return TheForkProvider(
        context=context,
        deps=deps,
    )


default_registry.register(
    ProviderType.THEFORK,
    build_thefork_provider,
)


if TYPE_CHECKING:
    _conforms: type[ReservationProvider] = TheForkProvider