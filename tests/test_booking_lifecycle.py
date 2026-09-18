"""Focused tests for the Alias booking lifecycle."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError
from app.intelligence.schemas import IntelligenceApplyReoptimizationRequest
from app.intelligence.sqlalchemy_service import IntelligenceOptimizationService
from app.models.reservation import ReservationStatus
from app.schemas.reservation import ReservationCreate
from app.services.ai_suggestion_service import AISuggestionService
from app.services.reservation_service import ReservationService


class FakeReservationRepository:
    def __init__(self):
        self.db = None
        self.created = []

    async def create(self, reservation):
        if reservation.id is None:
            reservation.id = uuid4()
        self.created.append(reservation)
        return reservation

    async def replace_table_assignments(
        self,
        *,
        reservation,
        table_ids,
        primary_table_id,
    ):
        reservation.table_id = primary_table_id
        return reservation


class FakeRestaurantRepository:
    async def get_by_id(self, restaurant_id):
        return None


class FakeTableRepository:
    pass


class FakeEmailService:
    def __init__(self):
        self.send_reservation_confirmation = AsyncMock()
        self.send_restaurant_reservation_notification = AsyncMock()


class FakeScalarCollection:
    def __init__(self, items):
        self.items = items

    def unique(self):
        return self

    def all(self):
        return list(self.items)


class FakeResult:
    def __init__(self, *, scalar=None, items=None):
        self.scalar = scalar
        self.items = [] if items is None else items

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return FakeScalarCollection(self.items)


class FakeApplySession:
    """Minimal async session for apply_reoptimization with no moved bookings."""

    def __init__(self, *, reservation, tables):
        self._results = [
            FakeResult(scalar=reservation),
            FakeResult(items=tables),
            FakeResult(items=[]),
            FakeResult(),
        ]
        self.added = []
        self.flush = AsyncMock()

    async def execute(self, statement):
        if not self._results:
            raise AssertionError("Unexpected extra database query")
        return self._results.pop(0)

    def add(self, item):
        self.added.append(item)


def _future_reservation_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=7)


def _payload(*, restaurant_id, customer_email="guest@example.com") -> ReservationCreate:
    return ReservationCreate(
        restaurant_id=restaurant_id,
        customer_name="Lifecycle Guest",
        customer_phone="+15551234567",
        customer_email=customer_email,
        party_size=4,
        reservation_time=_future_reservation_time(),
        duration_minutes=90,
    )


def _build_service():
    repository = FakeReservationRepository()
    email_service = FakeEmailService()

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(),
        table_repository=FakeTableRepository(),
        email_service=email_service,
        intelligence_service=SimpleNamespace(),
    )

    service._validate_reservation_time = AsyncMock()
    service._enforce_capacity = AsyncMock()
    service._record_reservation_event = AsyncMock()

    return service, repository, email_service


@pytest.mark.asyncio
async def test_direct_booking_is_confirmed_and_sends_confirmation():
    restaurant_id = uuid4()
    table_id = uuid4()

    service, repository, email_service = _build_service()

    service._assign_tables_with_aie = AsyncMock(
        return_value=(table_id, [table_id]),
    )
    service._reoptimization_available = AsyncMock(return_value=False)

    reservation = await service.create_reservation(
        _payload(restaurant_id=restaurant_id),
    )

    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.table_id == table_id
    assert len(repository.created) == 1

    email_service.send_reservation_confirmation.assert_awaited_once()
    service._reoptimization_available.assert_not_awaited()


@pytest.mark.asyncio
async def test_reoptimization_booking_is_pending_creates_suggestion_and_sends_no_confirmation(
    monkeypatch,
):
    restaurant_id = uuid4()

    service, repository, email_service = _build_service()

    service._assign_tables_with_aie = AsyncMock(
        return_value=(None, []),
    )
    service._reoptimization_available = AsyncMock(return_value=True)

    analyze_reservation = AsyncMock(return_value=object())
    monkeypatch.setattr(
        AISuggestionService,
        "analyze_reservation",
        analyze_reservation,
    )

    reservation = await service.create_reservation(
        _payload(restaurant_id=restaurant_id),
    )

    assert reservation.status == ReservationStatus.PENDING
    assert reservation.table_id is None
    assert len(repository.created) == 1

    analyze_reservation.assert_awaited_once_with(reservation)
    email_service.send_reservation_confirmation.assert_not_awaited()
    email_service.send_restaurant_reservation_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_unavailable_booking_is_not_created_and_sends_no_confirmation():
    restaurant_id = uuid4()

    service, repository, email_service = _build_service()

    service._assign_tables_with_aie = AsyncMock(
        return_value=(None, []),
    )
    service._reoptimization_available = AsyncMock(return_value=False)

    with pytest.raises(
        ConflictError,
        match="safe seating plan",
    ):
        await service.create_reservation(
            _payload(restaurant_id=restaurant_id),
        )

    assert repository.created == []
    email_service.send_reservation_confirmation.assert_not_awaited()
    email_service.send_restaurant_reservation_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_reoptimization_promotes_pending_reservation_to_confirmed():
    restaurant_id = uuid4()
    reservation_id = uuid4()
    table_id = uuid4()
    service_area_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
        party_size=4,
        reservation_time=_future_reservation_time(),
        duration_minutes=90,
        table_id=None,
    )

    table = SimpleNamespace(
        id=table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=4,
        table_number="12",
        is_active=True,
    )

    session = FakeApplySession(
        reservation=pending_reservation,
        tables=[table],
    )

    service = IntelligenceOptimizationService()

    result = await service.apply_reoptimization(
        session=session,
        payload=IntelligenceApplyReoptimizationRequest(
            new_reservation_id=reservation_id,
            new_reservation_table_ids=[table_id],
            new_reservation_primary_table_id=table_id,
            moves=[],
        ),
        allowed_restaurant_ids=[restaurant_id],
    )

    assert pending_reservation.status == ReservationStatus.CONFIRMED
    assert pending_reservation.table_id == table_id
    assert result.new_reservation_id == reservation_id
    assert result.new_reservation_primary_table_id == table_id
    assert result.new_reservation_table_ids == [table_id]
    assert result.applied_moves == []
    assert len(session.added) == 1
    session.flush.assert_awaited_once()

@pytest.mark.asyncio
async def test_reoptimization_booking_passes_suggestion_to_autopilot(
    monkeypatch,
):
    restaurant_id = uuid4()

    service, repository, email_service = _build_service()

    service._assign_tables_with_aie = AsyncMock(
        return_value=(None, []),
    )
    service._reoptimization_available = AsyncMock(
        return_value=True,
    )

    suggestion = SimpleNamespace(
        id=uuid4(),
    )

    analyze_reservation = AsyncMock(
        return_value=suggestion,
    )

    monkeypatch.setattr(
        AISuggestionService,
        "analyze_reservation",
        analyze_reservation,
    )

    autopilot_attempt = AsyncMock(
        side_effect=lambda *, reservation, suggestion: reservation,
    )

    service._try_autopilot_reoptimization = autopilot_attempt

    reservation = await service.create_reservation(
        _payload(
            restaurant_id=restaurant_id,
        ),
    )

    assert reservation.status == ReservationStatus.PENDING

    analyze_reservation.assert_awaited_once_with(
        reservation,
    )

    autopilot_attempt.assert_awaited_once_with(
        reservation=reservation,
        suggestion=suggestion,
    )

    email_service.send_reservation_confirmation.assert_not_awaited()
    email_service.send_restaurant_reservation_notification.assert_not_awaited()