from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.providers.contract.availability import (
    AliasVenueId,
    AvailabilityQuery,
    AvailabilityResult,
    Channel,
    TimeRange,
)
from app.services.alias_connect_reservation_service import (
    AliasConnectReservationService,
)

from datetime import timedelta

from app.providers.contract.guest import GuestInput, GuestProfile
from app.providers.contract.refs import IdempotencyKey, ProviderRef, ProviderType
from app.providers.contract.reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    Reservation,
    ReservationStatus,
    ReservationChanges,
    UpdateReservationRequest,
)

from app.providers.contract.capabilities import (
    ProviderCapabilities,
)
from app.providers.contract.errors import UnsupportedOperation, ProviderNotFound, UnknownProviderError

class FakeProvider:
    provider_type = ProviderType.SEVENROOMS
    capabilities = ProviderCapabilities(
        create=True,
        modify=True,
        cancel=True,
    )
    async def get_availability(
        self,
        query: AvailabilityQuery,
    ) -> AvailabilityResult:
        return AvailabilityResult(
            slots=[],
            queried_at=datetime.now(UTC),
        )

    async def create_reservation(
        self,
        request: CreateReservationRequest,
    ) -> Reservation:
        return Reservation(
            ref=ProviderRef(
                provider=ProviderType.SEVENROOMS,
                external_id="created-123",
            ),
            status=ReservationStatus.CONFIRMED,
            guest=GuestProfile(
                full_name=request.guest.full_name,
                phone=request.guest.phone,
                email=request.guest.email,
                notes=request.guest.notes,
            ),
            party_size=request.party_size,
            start=request.start,
            duration=request.duration,
            special_requests=request.special_requests,
            tags=request.tags,
            source=ProviderType.SEVENROOMS,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    
    async def get_reservation(
        self,
        ref: ProviderRef,
    ) -> Reservation | None:
        return Reservation(
            ref=ref,
            status=ReservationStatus.CONFIRMED,
            guest=GuestProfile(
                full_name="Found Guest",
                email="found@example.com",
            ),
            party_size=2,
            start=datetime(2026, 7, 1, 19, 30, tzinfo=UTC),
            duration=timedelta(minutes=90),
            source=ref.provider,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    
    async def update_reservation(
        self,
        request: UpdateReservationRequest,
    ) -> Reservation:
        return Reservation(
            ref=request.ref,
            status=ReservationStatus.CONFIRMED,
            guest=GuestProfile(
                full_name="Updated Guest",
                email="updated@example.com",
            ),
            party_size=request.changes.party_size or 2,
            start=request.changes.start or datetime(2026, 7, 1, 19, 30, tzinfo=UTC),
            duration=request.changes.duration,
            special_requests=request.changes.special_requests,
            tags=request.changes.tags or [],
            source=request.ref.provider,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    
    async def cancel_reservation(
        self,
        request: CancelReservationRequest,
    ) -> Reservation:
        return Reservation(
            ref=request.ref,
            status=ReservationStatus.CANCELLED,
            guest=GuestProfile(
                full_name="Cancelled Guest",
                email="cancelled@example.com",
            ),
            party_size=2,
            start=datetime(2026, 7, 1, 19, 30, tzinfo=UTC),
            duration=timedelta(minutes=90),
            special_requests=request.reason,
            source=request.ref.provider,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

class FakeResolver:
    async def resolve(
        self,
        session,
        venue_id,
    ):
        return FakeProvider()
    
class FakeOperation:
    def __init__(self):
        self.external_ref = None
        self.error_detail = None


class FakeOperationStore:
    def __init__(self, session):
        self.created = False
        self.succeeded = False
        self.failed = False

    async def create_operation(self, **kwargs):
        self.created = True
        return FakeOperation()

    async def mark_succeeded(
        self,
        operation,
        *,
        external_ref=None,
    ):
        self.succeeded = True
        operation.external_ref = external_ref
        return operation

    async def mark_failed(
        self,
        operation,
        *,
        error_detail=None,
    ):
        self.failed = True
        operation.error_detail = error_detail
        return operation
    
class FakeProviderWithoutCreate(FakeProvider):
    capabilities = ProviderCapabilities()


class FakeResolverWithoutCreate:
    async def resolve(
        self,
        session,
        venue_id,
    ):
        return FakeProviderWithoutCreate()
    
class FakeProviderWithoutModify(FakeProvider):
    capabilities = ProviderCapabilities(
        create=True,
        modify=False,
        cancel=True,
    )


class FakeResolverWithoutModify:
    async def resolve(self, session, venue_id):
        return FakeProviderWithoutModify()


class FakeProviderWithoutCancel(FakeProvider):
    capabilities = ProviderCapabilities(
        create=True,
        modify=True,
        cancel=False,
    )


class FakeResolverWithoutCancel:
    async def resolve(self, session, venue_id):
        return FakeProviderWithoutCancel()
    
class FakeProviderRaisesProviderError(FakeProvider):
    async def get_reservation(self, ref: ProviderRef) -> Reservation | None:
        raise ProviderNotFound("Reservation not found")


class FakeResolverRaisesProviderError:
    async def resolve(self, session, venue_id):
        return FakeProviderRaisesProviderError()


class FakeProviderRaisesUnexpectedError(FakeProvider):
    async def get_reservation(self, ref: ProviderRef) -> Reservation | None:
        raise RuntimeError("Raw provider crash")


class FakeResolverRaisesUnexpectedError:
    async def resolve(self, session, venue_id):
        return FakeProviderRaisesUnexpectedError()


@pytest.mark.asyncio
async def test_service_resolves_provider_for_availability():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolver(),
    )

    result = await service.get_availability(
        AvailabilityQuery(
            venue_id=AliasVenueId(
                UUID("11111111-1111-1111-1111-111111111111")
            ),
            party_size=2,
            window=TimeRange(
                start=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
                end=datetime(2026, 7, 1, 22, 0, tzinfo=UTC),
            ),
            channel=Channel.CONCIERGE_CHAT,
        )
    )

    assert isinstance(result, AvailabilityResult)
    assert result.slots == []

@pytest.mark.asyncio
async def test_service_resolves_provider_for_create_reservation():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolver(),
        operation_store_factory=FakeOperationStore,
    )

    reservation = await service.create_reservation(
        CreateReservationRequest(
            venue_id=AliasVenueId(
                UUID("11111111-1111-1111-1111-111111111111")
            ),
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
            client_token=IdempotencyKey(value="create-token-123"),
        )
    )

    assert reservation.ref.external_id == "created-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.guest.full_name == "Test Guest"

@pytest.mark.asyncio
async def test_service_resolves_provider_for_get_reservation():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolver(),
    )

    reservation = await service.get_reservation(
        AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
        ProviderRef(
            provider=ProviderType.SEVENROOMS,
            external_id="found-123",
        ),
    )

    assert reservation is not None
    assert reservation.ref.external_id == "found-123"
    assert reservation.guest.full_name == "Found Guest"

@pytest.mark.asyncio
async def test_service_resolves_provider_for_update_reservation():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolver(),
    )

    reservation = await service.update_reservation(
        AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
        UpdateReservationRequest(
            ref=ProviderRef(
                provider=ProviderType.SEVENROOMS,
                external_id="updated-123",
            ),
            changes=ReservationChanges(
                party_size=3,
                special_requests="Updated request",
            ),
            client_token=IdempotencyKey(value="update-token-123"),
        ),
    )

    assert reservation.ref.external_id == "updated-123"
    assert reservation.party_size == 3
    assert reservation.guest.full_name == "Updated Guest"
    assert reservation.special_requests == "Updated request"

@pytest.mark.asyncio
async def test_service_resolves_provider_for_cancel_reservation():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolver(),
    )

    reservation = await service.cancel_reservation(
        AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
        CancelReservationRequest(
            ref=ProviderRef(
                provider=ProviderType.SEVENROOMS,
                external_id="cancelled-123",
            ),
            reason="Guest requested cancellation",
            client_token=IdempotencyKey(value="cancel-token-123"),
        ),
    )

    assert reservation.ref.external_id == "cancelled-123"
    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.guest.full_name == "Cancelled Guest"
    assert reservation.special_requests == "Guest requested cancellation"

@pytest.mark.asyncio
async def test_create_reservation_fails_when_capability_not_supported():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolverWithoutCreate(),
    )

    with pytest.raises(UnsupportedOperation):
        await service.create_reservation(
            CreateReservationRequest(
                venue_id=AliasVenueId(
                    UUID("11111111-1111-1111-1111-111111111111")
                ),
                guest=GuestInput(
                    full_name="Test Guest",
                    email="guest@example.com",
                ),
                party_size=2,
                start=datetime(2026, 7, 1, 19, 30, tzinfo=UTC),
                duration=timedelta(minutes=90),
                channel=Channel.CONCIERGE_CHAT,
                client_token=IdempotencyKey(value="capability-test"),
            )
        )

@pytest.mark.asyncio
async def test_update_reservation_fails_when_capability_not_supported():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolverWithoutModify(),
    )

    with pytest.raises(UnsupportedOperation):
        await service.update_reservation(
            AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
            UpdateReservationRequest(
                ref=ProviderRef(
                    provider=ProviderType.SEVENROOMS,
                    external_id="update-test",
                ),
                changes=ReservationChanges(
                    party_size=4,
                ),
                client_token=IdempotencyKey(value="update-capability"),
            ),
        )

@pytest.mark.asyncio
async def test_cancel_reservation_fails_when_capability_not_supported():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolverWithoutCancel(),
    )

    with pytest.raises(UnsupportedOperation):
        await service.cancel_reservation(
            AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
            CancelReservationRequest(
                ref=ProviderRef(
                    provider=ProviderType.SEVENROOMS,
                    external_id="cancel-test",
                ),
                reason="Test",
                client_token=IdempotencyKey(value="cancel-capability"),
            ),
        )

@pytest.mark.asyncio
async def test_service_preserves_normalized_provider_errors():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolverRaisesProviderError(),
    )

    with pytest.raises(ProviderNotFound):
        await service.get_reservation(
            AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
            ProviderRef(
                provider=ProviderType.SEVENROOMS,
                external_id="missing-123",
            ),
        )


@pytest.mark.asyncio
async def test_service_wraps_unexpected_provider_errors():
    service = AliasConnectReservationService(
        session=None,
        resolver=FakeResolverRaisesUnexpectedError(),
    )

    with pytest.raises(UnknownProviderError):
        await service.get_reservation(
            AliasVenueId(UUID("11111111-1111-1111-1111-111111111111")),
            ProviderRef(
                provider=ProviderType.SEVENROOMS,
                external_id="boom-123",
            ),
        )