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
    ) -> None:
        self._context = context
        self._deps = deps
        credentials = context.credentials or {}
        settings = context.settings or {}

        self._client = SevenRoomsClient(
            SevenRoomsClientConfig(
                api_key=credentials.get("api_key"),
                venue_id=settings.get("venue_id"),
            )
        )

    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        raise NotImplementedError("SevenRooms availability not implemented yet")

    async def create_reservation(
        self,
        request: CreateReservationRequest,
    ) -> Reservation:
        raise NotImplementedError("SevenRooms create not implemented yet")

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
        raise NotImplementedError("SevenRooms get not implemented yet")

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