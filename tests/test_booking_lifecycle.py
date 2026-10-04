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
from app.core.exceptions import (
    ConflictError,
    ValidationError,
)


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
        return SimpleNamespace(
            id=restaurant_id,
            name="Test Restaurant",
            timezone="UTC",
            preferred_language="en",
            email="restaurant@example.com",
            autopilot_enabled=False,
        )


class FakeTableRepository:
    pass


class FakeEmailService:
    def __init__(self):
        self.send_reservation_confirmation = AsyncMock()
        self.send_restaurant_reservation_notification = AsyncMock()

        self.send_reservation_pending_confirmation = AsyncMock()
        self.send_restaurant_pending_reservation_notification = AsyncMock()


class FakeScalarCollection:
    def __init__(self, items):
        self.items = items

    def unique(self):
        return self

    def all(self):
        return list(self.items)

    def first(self):
        return self.items[0] if self.items else None


class FakeResult:
    def __init__(self, *, scalar=None, items=None):
        self.scalar = scalar
        self.items = [] if items is None else items

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return FakeScalarCollection(self.items)


class FakeApplySession:
    """Minimal async session for apply_reoptimization."""

    def __init__(
        self,
        *,
        reservation,
        live_seated_reservation=None,
        moved_reservations=None,
        tables,
        suggestion=None,
        conflicting_reservations=None,
    ):
        self.reservation = reservation
        self.tables = tables
        self.suggestion = suggestion
        self.live_seated_reservation = live_seated_reservation
        self.moved_reservations = list(
            moved_reservations or []
        )
        self.conflicting_reservations = (
            []
            if conflicting_reservations is None
            else conflicting_reservations
        )

        self._results = [
            FakeResult(
                scalar=reservation,
            ),
            FakeResult(
                items=tables,
            ),
            FakeResult(
                items=self.conflicting_reservations,
            ),
            FakeResult(),
        ]

        self.added = []
        self.flush = AsyncMock()

    async def execute(
        self,
        statement,
    ):
        statement_text = str(statement)

        if (
            "FROM tables" in statement_text
            and "FOR UPDATE" in statement_text
        ):
            return FakeResult(
                items=self.tables,
            )

        if (
            "FROM reservations" in statement_text
            and "reservation_table_assignments" in statement_text
            and "seated" in statement_text.lower()
        ):
            return FakeResult(
                items=(
                    [self.live_seated_reservation]
                    if self.live_seated_reservation is not None
                    else []
                ),
            )

        if (
            self.moved_reservations
            and "FROM reservations" in statement_text
            and "reservations.id IN" in statement_text
            and "reservations.restaurant_id" in statement_text
        ):
            return FakeResult(
                items=self.moved_reservations,
            )

        if (
            self.suggestion is not None
            and "ai_suggestions" in statement_text
        ):
            return FakeResult(
                scalar=self.suggestion,
            )

        if not self._results:
            raise AssertionError(
                "Unexpected extra database query"
            )

        return self._results.pop(0)

    def add(
        self,
        item,
    ):
        self.added.append(item)

def _future_reservation_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=7)


def _payload(
    *,
    restaurant_id,
    customer_email="guest@example.com",
) -> ReservationCreate:
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

    analyze_reservation = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid4(),
            payload={},
        )
    )
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
    email_service.send_reservation_pending_confirmation.assert_awaited_once()
    email_service.send_restaurant_pending_reservation_notification.assert_awaited_once()


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
async def test_apply_modification_reoptimization_updates_same_reservation_requested_state():
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    old_table_id = uuid4()
    new_table_id = uuid4()
    service_area_id = uuid4()

    original_time = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    requested_time = (
        original_time
        + timedelta(hours=1)
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=original_time,
        duration_minutes=90,
        table_id=old_table_id,
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "reservation": {
                "id": str(reservation_id),
                "party_size": 6,
                "reservation_time": (
                    original_time.isoformat()
                ),
                "duration_minutes": 90,
                "status": "confirmed",
                "primary_table_id": str(
                    old_table_id
                ),
                "table_ids": [
                    str(old_table_id),
                ],
            },
            "requested_modification": {
                "party_size": 10,
                "reservation_time": (
                    requested_time.isoformat()
                ),
            },
            "plan": {},
        },
    )

    table = SimpleNamespace(
        id=new_table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=10,
        table_number="20",
        is_active=True,
    )

    session = FakeApplySession(
        reservation=reservation,
        tables=[table],
        suggestion=suggestion,
    )

    service = IntelligenceOptimizationService()

    result = await service.apply_reoptimization(
        session=session,
        payload=IntelligenceApplyReoptimizationRequest(
            suggestion_id=suggestion_id,
            new_reservation_id=reservation_id,
            new_reservation_table_ids=[
                new_table_id,
            ],
            new_reservation_primary_table_id=(
                new_table_id
            ),
            moves=[],
        ),
        allowed_restaurant_ids=[
            restaurant_id,
        ],
    )

    assert reservation.id == reservation_id
    assert reservation.party_size == 10
    assert (
        reservation.reservation_time
        == requested_time
    )
    assert (
        reservation.status
        == ReservationStatus.CONFIRMED
    )
    assert reservation.table_id == new_table_id

    assert result.new_reservation_id == reservation_id
    assert (
        result.new_reservation_primary_table_id
        == new_table_id
    )

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

@pytest.mark.asyncio
async def test_direct_aie_capacity_is_not_blocked_by_legacy_aggregate_capacity():
    """
    LAB-006 regression.

    When Alias Intelligence has a valid executable seating assignment,
    customer-facing availability must not be rejected by the legacy
    aggregate capacity heuristic before AIE is evaluated.

    Capacity truth for direct booking must remain aligned with the
    operational optimizer.
    """
    restaurant_id = uuid4()
    table_2_id = uuid4()
    table_3_id = uuid4()

    repository = FakeReservationRepository()
    repository.list_in_window = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid4(),
                party_size=75,
            ),
        ],
    )

    restaurant_repository = FakeRestaurantRepository()
    restaurant_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            number_of_tables=20,
        ),
    )

    intelligence_service = SimpleNamespace(
        optimize=AsyncMock(
            return_value=SimpleNamespace(
                available=True,
                recommended=SimpleNamespace(
                    table_ids=[
                        table_3_id,
                        table_2_id,
                    ],
                ),
            ),
        ),
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=restaurant_repository,
        table_repository=FakeTableRepository(),
        email_service=FakeEmailService(),
        intelligence_service=intelligence_service,
    )

    service._validate_reservation_time = AsyncMock()

    outcome = await service.assess_booking_availability(
        reservation_time=_future_reservation_time(),
        party_size=10,
        restaurant_id=restaurant_id,
        duration_minutes=90,
    )

    assert outcome.value == "direct_available"

    intelligence_service.optimize.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_reservation_aie_assignment_is_not_blocked_by_legacy_capacity():
    """
    LAB-006 regression.

    A valid executable AIE assignment must be allowed to create the
    reservation even when the legacy aggregate-capacity heuristic would
    reject the same request.
    """
    restaurant_id = uuid4()
    table_2_id = uuid4()
    table_3_id = uuid4()

    repository = FakeReservationRepository()
    repository.list_in_window = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid4(),
                party_size=75,
            ),
        ],
    )

    restaurant_repository = FakeRestaurantRepository()
    restaurant_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            number_of_tables=20,
        ),
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=restaurant_repository,
        table_repository=FakeTableRepository(),
        email_service=FakeEmailService(),
        intelligence_service=SimpleNamespace(),
    )

    service._validate_reservation_time = AsyncMock()

    service._assign_tables_with_aie = AsyncMock(
        return_value=(
            table_3_id,
            [table_3_id, table_2_id],
        ),
    )

    service._record_reservation_event = AsyncMock()
    service._try_record_temporal_prediction = AsyncMock()

    reservation = await service.create_reservation(
        ReservationCreate(
            restaurant_id=restaurant_id,
            customer_name="LAB-006 Guest",
            customer_phone="+15551234567",
            customer_email="guest@example.com",
            party_size=10,
            reservation_time=_future_reservation_time(),
            duration_minutes=90,
        ),
    )

    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.table_id == table_3_id

    service._assign_tables_with_aie.assert_awaited_once()

    assert repository.created

@pytest.mark.asyncio
async def test_apply_modification_reoptimization_validates_capacity_against_requested_party_size():
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    old_table_id = uuid4()
    target_table_id = uuid4()
    service_area_id = uuid4()

    reservation_time = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=reservation_time,
        duration_minutes=90,
        table_id=old_table_id,
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "reservation": {
                "id": str(reservation_id),
                "party_size": 6,
                "reservation_time": (
                    reservation_time.isoformat()
                ),
                "duration_minutes": 90,
                "status": "confirmed",
                "primary_table_id": str(
                    old_table_id
                ),
                "table_ids": [
                    str(old_table_id),
                ],
            },
            "requested_modification": {
                "party_size": 10,
                "reservation_time": (
                    reservation_time.isoformat()
                ),
            },
            "plan": {},
        },
    )

    # Valid for the old party size (6), but NOT for
    # the requested modification party size (10).
    target_table = SimpleNamespace(
        id=target_table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=6,
        table_number="20",
        is_active=True,
    )

    session = FakeApplySession(
        reservation=reservation,
        tables=[
            target_table,
        ],
        suggestion=suggestion,
    )

    service = IntelligenceOptimizationService()

    with pytest.raises(
        ValidationError,
        match="do not have enough capacity",
    ):
        await service.apply_reoptimization(
            session=session,
            payload=IntelligenceApplyReoptimizationRequest(
                suggestion_id=suggestion_id,
                new_reservation_id=reservation_id,
                new_reservation_table_ids=[
                    target_table_id,
                ],
                new_reservation_primary_table_id=(
                    target_table_id
                ),
                moves=[],
            ),
            allowed_restaurant_ids=[
                restaurant_id,
            ],
        )

    assert reservation.id == reservation_id
    assert reservation.party_size == 6
    assert (
        reservation.reservation_time
        == reservation_time
    )
    assert reservation.table_id == old_table_id
    assert (
        reservation.status
        == ReservationStatus.CONFIRMED
    )

@pytest.mark.asyncio
async def test_apply_modification_reoptimization_validates_collision_at_requested_time():
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()

    old_table_id = uuid4()
    target_table_id = uuid4()
    conflicting_reservation_id = uuid4()

    service_area_id = uuid4()

    original_time = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    requested_time = (
        original_time
        + timedelta(hours=3)
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=original_time,
        duration_minutes=90,
        table_id=old_table_id,
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "reservation": {
                "id": str(reservation_id),
                "party_size": 6,
                "reservation_time": (
                    original_time.isoformat()
                ),
                "duration_minutes": 90,
                "status": "confirmed",
                "primary_table_id": str(
                    old_table_id
                ),
                "table_ids": [
                    str(old_table_id),
                ],
            },
            "requested_modification": {
                "party_size": 10,
                "reservation_time": (
                    requested_time.isoformat()
                ),
            },
            "plan": {},
        },
    )

    target_table = SimpleNamespace(
        id=target_table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=10,
        table_number="20",
        is_active=True,
    )

    # This booking conflicts with the TARGET table at the
    # requested modification time, but not at the original
    # reservation time.
    conflicting_reservation = SimpleNamespace(
        id=conflicting_reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=2,
        reservation_time=(
            requested_time
            + timedelta(minutes=15)
        ),
        duration_minutes=90,
        table_id=target_table_id,
        assigned_table_ids=[
            target_table_id,
        ],
    )

    session = FakeApplySession(
        reservation=reservation,
        tables=[
            target_table,
        ],
        suggestion=suggestion,
        conflicting_reservations=[
            conflicting_reservation,
        ],
    )

    service = IntelligenceOptimizationService()

    with pytest.raises(
        ValidationError,
    ):
        await service.apply_reoptimization(
            session=session,
            payload=IntelligenceApplyReoptimizationRequest(
                suggestion_id=suggestion_id,
                new_reservation_id=reservation_id,
                new_reservation_table_ids=[
                    target_table_id,
                ],
                new_reservation_primary_table_id=(
                    target_table_id
                ),
                moves=[],
            ),
            allowed_restaurant_ids=[
                restaurant_id,
            ],
        )

    # Fail closed: the customer's valid confirmed booking
    # must remain completely untouched.
    assert reservation.id == reservation_id
    assert reservation.party_size == 6
    assert (
        reservation.reservation_time
        == original_time
    )
    assert reservation.table_id == old_table_id
    assert (
        reservation.status
        == ReservationStatus.CONFIRMED
    )

    # Physical mutation must not have started.
    assert session.added == []
    session.flush.assert_not_awaited()

@pytest.mark.asyncio
async def test_apply_reoptimization_rejects_live_seated_occupancy_after_expected_end():
    restaurant_id = uuid4()
    target_reservation_id = uuid4()
    seated_reservation_id = uuid4()
    table_id = uuid4()
    service_area_id = uuid4()

    seated_start = _future_reservation_time()
    target_start = seated_start + timedelta(minutes=90)

    target_reservation = SimpleNamespace(
        id=target_reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=2,
        reservation_time=target_start,
        duration_minutes=90,
        table_id=table_id,
    )

    seated_reservation = SimpleNamespace(
        id=seated_reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.SEATED,
        party_size=2,
        reservation_time=seated_start,
        duration_minutes=90,
        table_id=table_id,
        assigned_table_ids=[table_id],
    )

    table = SimpleNamespace(
        id=table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=2,
        table_number="43",
        is_active=True,
    )

    session = FakeApplySession(
        reservation=target_reservation,
        tables=[table],
        live_seated_reservation=seated_reservation,
    )

    service = IntelligenceOptimizationService()

    with pytest.raises(
        ValidationError,
        match="occupied",
    ):
        await service.apply_reoptimization(
            session=session,
            payload=IntelligenceApplyReoptimizationRequest(
                new_reservation_id=target_reservation_id,
                new_reservation_table_ids=[table_id],
                new_reservation_primary_table_id=table_id,
                moves=[],
            ),
            allowed_restaurant_ids=[restaurant_id],
        )

    assert target_reservation.status == ReservationStatus.CONFIRMED
    assert target_reservation.table_id == table_id
    session.flush.assert_not_awaited()

@pytest.mark.asyncio
async def test_apply_reoptimization_rejects_target_that_became_seated():
    restaurant_id = uuid4()
    reservation_id = uuid4()
    table_id = uuid4()
    service_area_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.SEATED,
        party_size=2,
        reservation_time=_future_reservation_time(),
        duration_minutes=90,
        table_id=table_id,
    )

    table = SimpleNamespace(
        id=table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=2,
        table_number="43",
        is_active=True,
    )

    session = FakeApplySession(
        reservation=reservation,
        tables=[table],
    )

    service = IntelligenceOptimizationService()

    with pytest.raises(
        ValidationError,
        match="seated",
    ):
        await service.apply_reoptimization(
            session=session,
            payload=IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservation_id,
                new_reservation_table_ids=[table_id],
                new_reservation_primary_table_id=table_id,
                moves=[],
            ),
            allowed_restaurant_ids=[restaurant_id],
        )

    assert reservation.status == ReservationStatus.SEATED
    assert reservation.table_id == table_id
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_reoptimization_rejects_move_of_seated_reservation():
    restaurant_id = uuid4()
    target_reservation_id = uuid4()
    moved_reservation_id = uuid4()
    target_table_id = uuid4()
    moved_table_id = uuid4()
    service_area_id = uuid4()

    target_reservation = SimpleNamespace(
        id=target_reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=2,
        reservation_time=_future_reservation_time(),
        duration_minutes=90,
        table_id=target_table_id,
    )

    target_table = SimpleNamespace(
        id=target_table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=2,
        table_number="43",
        is_active=True,
    )

    moved_table = SimpleNamespace(
        id=moved_table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        seats=2,
        table_number="44",
        is_active=True,
    )

    session = FakeApplySession(
        reservation=target_reservation,
        tables=[
            target_table,
            moved_table,
        ],
        moved_reservations=[
            SimpleNamespace(
                id=moved_reservation_id,
                restaurant_id=restaurant_id,
                status=ReservationStatus.SEATED,
                party_size=2,
                reservation_time=_future_reservation_time(),
                duration_minutes=90,
                table_id=moved_table_id,
            ),
        ],
    )

    service = IntelligenceOptimizationService()

    with pytest.raises(
        ValidationError,
        match="seated",
    ):
        await service.apply_reoptimization(
            session=session,
            payload=IntelligenceApplyReoptimizationRequest(
                new_reservation_id=target_reservation_id,
                new_reservation_table_ids=[target_table_id],
                new_reservation_primary_table_id=target_table_id,
                moves=[
                    {
                        "reservation_id": moved_reservation_id,
                        "to_table_ids": [moved_table_id],
                        "primary_table_id": moved_table_id,
                    }
                ],
            ),
            allowed_restaurant_ids=[restaurant_id],
        )