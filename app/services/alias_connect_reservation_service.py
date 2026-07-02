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

from app.providers.contract.errors import (
    ProviderError,
    UnknownProviderError,
    UnsupportedOperation,
)

from collections.abc import Callable

from app.models.integration import OperationType
from app.providers.operation_store import SqlAlchemyOperationStore


class AliasConnectReservationService:
    def __init__(
        self,
        session: AsyncSession,
        resolver: ProviderResolver | None = None,
        operation_store_factory: Callable[[AsyncSession], SqlAlchemyOperationStore] | None = None,
    ) -> None:
        self._session = session
        self._resolver = resolver or ProviderResolver()
        self._operation_store_factory = (
            operation_store_factory or SqlAlchemyOperationStore
        )

    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        provider = await self._resolver.resolve(
            self._session,
            query.venue_id,
        )
        return await self._execute_provider_operation(
            lambda: provider.get_availability(query)
        )

    async def get_reservation(
        self,
        venue_id,
        ref: ProviderRef,
    ) -> Reservation | None:
        provider = await self._resolver.resolve(
            self._session,
            venue_id,
        )
        return await self._execute_provider_operation(
            lambda: provider.get_reservation(ref)
        )

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

        store = self._operation_store()
        operation = await store.create_operation(
            idempotency_key=str(request.client_token),
            restaurant_id=request.venue_id,
            provider_type=provider.provider_type,
            operation_type=OperationType.CREATE_RESERVATION,
        )

        try:
            reservation = await self._execute_provider_operation(
                lambda: provider.create_reservation(request)
            )
        except Exception as exc:
            await store.mark_failed(
                operation,
                error_detail=str(exc),
            )
            raise

        await store.mark_succeeded(
            operation,
            external_ref=reservation.ref.external_id,
        )

        return reservation
    

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

        store = self._operation_store()
        operation = await store.create_operation(
            idempotency_key=str(request.client_token),
            restaurant_id=venue_id,
            provider_type=provider.provider_type,
            operation_type=OperationType.UPDATE_RESERVATION,
        )

        try:
            reservation = await self._execute_provider_operation(
                lambda: provider.update_reservation(request)
            )
        except Exception as exc:
            await store.mark_failed(
                operation,
                error_detail=str(exc),
            )
            raise

        await store.mark_succeeded(
            operation,
            external_ref=reservation.ref.external_id,
        )

        return reservation

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

        store = self._operation_store()
        operation = await store.create_operation(
            idempotency_key=str(request.client_token),
            restaurant_id=venue_id,
            provider_type=provider.provider_type,
            operation_type=OperationType.CANCEL_RESERVATION,
        )

        try:
            reservation = await self._execute_provider_operation(
                lambda: provider.cancel_reservation(request)
            )
        except Exception as exc:
            await store.mark_failed(
                operation,
                error_detail=str(exc),
            )
            raise

        await store.mark_succeeded(
            operation,
            external_ref=reservation.ref.external_id,
        )

        return reservation
    
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
    
    async def _execute_provider_operation(
        self,
        operation,
    ):
        try:
            return await operation()
        except ProviderError:
            raise
        except Exception as exc:
            raise UnknownProviderError(
                "Unexpected provider operation failure",
            ) from exc
        
    def _operation_store(self) -> SqlAlchemyOperationStore:
        return self._operation_store_factory(self._session)