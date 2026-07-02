"""Provider-agnostic reservation orchestration.

This service is the single entrypoint used by the Concierge AI and future API
endpoints. It resolves the correct provider and delegates every operation
through the ReservationProvider contract.

No provider-specific logic belongs here.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.contract.availability import (
    AvailabilityQuery,
    AvailabilityResult,
)
from app.providers.contract.refs import ProviderRef
from app.providers.contract.reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    Reservation,
    UpdateReservationRequest,
)
from app.providers.resolver import ProviderResolver

from app.providers.contract.errors import UnsupportedOperation


class AliasConnectReservationService:
    def __init__(
        self,
        session: AsyncSession,
        resolver: ProviderResolver | None = None,
    ) -> None:
        self._session = session
        self._resolver = resolver or ProviderResolver()

    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        provider = await self._resolver.resolve(
            self._session,
            query.venue_id,
        )
        return await provider.get_availability(query)

    async def get_reservation(
        self,
        venue_id,
        ref: ProviderRef,
    ) -> Reservation | None:
        provider = await self._resolver.resolve(
            self._session,
            venue_id,
        )
        return await provider.get_reservation(ref)

    async def create_reservation(
        self,
        request: CreateReservationRequest,
    ) -> Reservation:
        provider = await self._resolver.resolve(
            self._session,
            request.venue_id,
        )
        self._require_capability(
            provider.capabilities.create,
            "create_reservation",
            provider,
        )
        return await provider.create_reservation(request)
    

    async def update_reservation(
        self,
        venue_id,
        request: UpdateReservationRequest,
    ) -> Reservation:
        provider = await self._resolver.resolve(
            self._session,
            venue_id,
        )
        self._require_capability(
            provider.capabilities.modify,
            "update_reservation",
            provider,
        )
        return await provider.update_reservation(request)

    async def cancel_reservation(
        self,
        venue_id,
        request: CancelReservationRequest,
    ) -> Reservation:
        provider = await self._resolver.resolve(
            self._session,
            venue_id,
        )
        self._require_capability(
            provider.capabilities.cancel,
            "cancel_reservation",
            provider,
        )
        return await provider.cancel_reservation(request)
    
    def _require_capability(
        self,
        supported: bool,
        operation: str,
        provider,
    ) -> None:
        if supported:
            return

        raise UnsupportedOperation(
            f"Provider does not support operation: {operation}",
        )