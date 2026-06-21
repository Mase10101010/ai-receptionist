import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from collections.abc import Iterator

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.services.email_service import EmailService
from app.services.reservation_service import ReservationService

from . import mapper
from ..context import ProviderContext, ProviderDependencies
from ..contract.availability import AvailabilityQuery, AvailabilityResult
from ..contract.base import ProviderHealth, ReservationProvider
from ..contract.capabilities import ProviderCapabilities, SourceOfTruth
from ..contract.errors import (
    ProviderError,
    ProviderNotFound,
    ProviderValidationError,
    SlotUnavailable,
    UnknownProviderError,
)
from ..contract.refs import ProviderRef, ProviderType
from ..contract.reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    Reservation,
    UpdateReservationRequest,
)
from ..registry import default_registry


_NATIVE_CAPABILITIES = ProviderCapabilities(
    real_time_availability=True,
    create=True,
    modify=True,
    cancel=True,
    custom_duration=True,
    request_to_book=False,
    waitlist=False,
    deposits=False,
    guest_recognition=False,
    webhooks=False,
    idempotency_keys=False,
)


def _map_native_error(exc: Exception) -> ProviderError:
    if isinstance(exc, NotFoundError):
        return ProviderNotFound(str(exc), provider=ProviderType.ALIAS_NATIVE)

    if isinstance(exc, ValidationError):
        return ProviderValidationError(str(exc), provider=ProviderType.ALIAS_NATIVE)

    if isinstance(exc, ConflictError):
        return SlotUnavailable(str(exc), provider=ProviderType.ALIAS_NATIVE)

    return UnknownProviderError(
        str(exc) or "Unexpected native provider error",
        provider=ProviderType.ALIAS_NATIVE,
    )


@contextmanager
def _translate_errors() -> Iterator[None]:
    try:
        yield
    except ProviderError:
        raise
    except Exception as exc:
        raise _map_native_error(exc) from exc


class AliasNativeProvider:
    capabilities: ProviderCapabilities = _NATIVE_CAPABILITIES
    source_of_truth: SourceOfTruth = SourceOfTruth.ALIAS

    def __init__(
        self,
        context: ProviderContext,
        service: ReservationService,
    ) -> None:
        self._context = context
        self._service = service

    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        with _translate_errors():
            requested_available = await self._service.check_availability(
                reservation_time=query.window.start,
                party_size=query.party_size,
                restaurant_id=query.venue_id,
            )

            alternatives = await self._service.suggest_alternative_slots(
                reservation_time=query.window.start,
                party_size=query.party_size,
                restaurant_id=query.venue_id,
            )

        return mapper.build_availability_result(
            window=query.window,
            requested_available=requested_available,
            alternatives=alternatives,
        )

    async def create_reservation(
        self,
        request: CreateReservationRequest,
    ) -> Reservation:
        payload = mapper.to_reservation_create(request)

        with _translate_errors():
            orm = await self._service.create_reservation(payload)

        return mapper.to_contract_reservation(orm)

    async def update_reservation(
        self,
        request: UpdateReservationRequest,
    ) -> Reservation:
        reservation_id = self._ref_to_uuid(request.ref)
        payload = mapper.to_reservation_update(request.changes)

        with _translate_errors():
            orm = await self._service.update_reservation(
                reservation_id=reservation_id,
                payload=payload,
            )

        return mapper.to_contract_reservation(orm)

    async def cancel_reservation(
        self,
        request: CancelReservationRequest,
    ) -> Reservation:
        reservation_id = self._ref_to_uuid(request.ref)

        with _translate_errors():
            orm = await self._service.cancel_reservation(reservation_id)

        return mapper.to_contract_reservation(orm)

    async def get_reservation(
        self,
        ref: ProviderRef,
    ) -> Reservation | None:
        reservation_id = self._ref_to_uuid(ref)

        try:
            orm = await self._service.get_reservation(
                reservation_id=reservation_id,
                restaurant_id=self._context.venue_id,
            )
        except NotFoundError:
            return None
        except Exception as exc:
            raise _map_native_error(exc) from exc

        return mapper.to_contract_reservation(orm)

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=ProviderType.ALIAS_NATIVE,
            healthy=True,
            checked_at=datetime.now(UTC),
        )

    def _ref_to_uuid(self, ref: ProviderRef) -> uuid.UUID:
        if ref.provider is not ProviderType.ALIAS_NATIVE:
            raise ProviderValidationError(
                f"Reference {ref} does not belong to Alias native provider",
                provider=ProviderType.ALIAS_NATIVE,
            )

        try:
            return uuid.UUID(ref.external_id)
        except ValueError as exc:
            raise ProviderValidationError(
                f"Invalid native reservation id: {ref.external_id!r}",
                provider=ProviderType.ALIAS_NATIVE,
            ) from exc


def build_native_provider(
    context: ProviderContext,
    deps: ProviderDependencies,
) -> AliasNativeProvider:
    reservation_repository = ReservationRepository(deps.session)
    restaurant_repository = RestaurantRepository(deps.session)
    table_repository = TableRepository(deps.session)
    email_service = EmailService()

    reservation_service = ReservationService(
        repository=reservation_repository,
        restaurant_repository=restaurant_repository,
        table_repository=table_repository,
        email_service=email_service,
    )

    return AliasNativeProvider(
        context=context,
        service=reservation_service,
    )


default_registry.register(
    ProviderType.ALIAS_NATIVE,
    build_native_provider,
)