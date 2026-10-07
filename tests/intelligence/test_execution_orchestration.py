"""Tests for Brain V1 execution orchestration.

These tests exercise the router-level orchestration directly:
gate -> physical apply -> suggestion acceptance -> audit -> commit.

They intentionally use small fakes so the test verifies orchestration order
without rebuilding the full database/optimizer stack.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime

from app.core.exceptions import ValidationError

import pytest

import app.intelligence.router as intelligence_router

from app.models.reservation import ReservationStatus
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
    IntelligenceApplyLiveSeatedModificationRequest,
)

import app.intelligence_execution.orchestrator as execution_orchestrator

from app.intelligence_events.models import (
    IntelligenceEventSource,
)


RESTAURANT_ID = uuid4()
RESERVATION_ID = uuid4()
SUGGESTION_ID = uuid4()
TABLE_ID = uuid4()
USER_ID = uuid4()


class FakeRestaurantRepository:
    def __init__(self, session):
        self.session = session

    async def list_by_owner(self, user_id):
        return [
            SimpleNamespace(
                id=RESTAURANT_ID,
                subscription_status="active",
            ),
        ]


class FakeReservationRepository:
    current_reservation = None

    def __init__(self, session):
        self.session = session

    async def get_by_id_for_restaurants(
        self,
        *,
        reservation_id,
        restaurant_ids,
    ):
        if (
            reservation_id != RESERVATION_ID
            or RESTAURANT_ID not in restaurant_ids
        ):
            return None

        if self.__class__.current_reservation is not None:
            return self.__class__.current_reservation

        return SimpleNamespace(
            id=RESERVATION_ID,
            restaurant_id=RESTAURANT_ID,
            status=ReservationStatus.PENDING,
            customer_email=None,
            party_size=10,
            reservation_time=datetime.fromisoformat(
                "2026-09-27T11:00:00+08:00"
            ),
            duration_minutes=90,
            table_id=TABLE_ID,
            assigned_table_ids=[TABLE_ID],
        )


class FakeSuggestionRepository:
    current_suggestion = None

    def __init__(self, session):
        self.session = session

    async def get_by_id(
        self,
        suggestion_id,
        restaurant_ids=None,
    ):
        if self.__class__.current_suggestion is not None:
            return self.__class__.current_suggestion

        return SimpleNamespace(
            id=SUGGESTION_ID,
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            payload={},
        )


class FakeExecutionGate:
    calls = []
    error = None

    def __init__(self, *, repository):
        self.repository = repository

    async def validate_reoptimization(self, **kwargs):
        self.__class__.calls.append(kwargs)

        if self.__class__.error is not None:
            raise self.__class__.error


class FakeAISuggestionService:
    accept_calls = []

    def __init__(
        self,
        *,
        repository,
        reservation_repository,
        intelligence_service=None,
    ):
        self.repository = repository
        self.reservation_repository = reservation_repository
        self.intelligence_service = intelligence_service

    async def accept(
        self,
        *,
        suggestion_id,
        restaurant_ids,
        source,
    ):
        self.__class__.accept_calls.append(
            {
                "suggestion_id": suggestion_id,
                "restaurant_ids": restaurant_ids,
                "source": source,
            },
        )

        return SimpleNamespace(
            id=suggestion_id,
        )


class FakeIntelligenceEventService:
    record_calls = []

    def __init__(self, *, repository):
        self.repository = repository

    async def record(self, **kwargs):
        self.__class__.record_calls.append(kwargs)
        return SimpleNamespace()


class FakeIntelligenceEventRepository:
    def __init__(self, session):
        self.session = session


class FakeOptimizationService:
    def __init__(self):
        self.apply_reoptimization = AsyncMock(
            return_value=IntelligenceApplyReoptimizationResponse(
                new_reservation_id=RESERVATION_ID,
                new_reservation_primary_table_id=TABLE_ID,
                new_reservation_table_ids=[TABLE_ID],
                new_reservation_table_numbers=["12"],
                applied_moves=[],
            ),
        )


class FailingOptimizationService:
    def __init__(self):
        self.apply_reoptimization = AsyncMock(
            side_effect=RuntimeError("apply failed"),
        )


class FakeSession:
    def __init__(self):
        self.commit = AsyncMock()

class FakeEmailService:
    confirmation_calls = []

    async def send_reservation_confirmation(self, **kwargs):
        self.__class__.confirmation_calls.append(kwargs)


def build_payload():
    return IntelligenceApplyReoptimizationRequest(
        suggestion_id=SUGGESTION_ID,
        new_reservation_id=RESERVATION_ID,
        new_reservation_table_ids=[TABLE_ID],
        new_reservation_primary_table_id=TABLE_ID,
        moves=[],
    )


def patch_router_dependencies(
    monkeypatch,
    *,
    optimization_service,
):
    FakeExecutionGate.calls = []
    FakeExecutionGate.error = None
    FakeReservationRepository.current_reservation = None
    FakeSuggestionRepository.current_suggestion = None
    FakeAISuggestionService.accept_calls = []
    FakeIntelligenceEventService.record_calls = []

    # Router boundary:
    # authorization + transaction ownership.
    monkeypatch.setattr(
        intelligence_router,
        "RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        intelligence_router,
        "ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        intelligence_router,
        "AISuggestionRepository",
        FakeSuggestionRepository,
    )
    monkeypatch.setattr(
        intelligence_router,
        "service",
        optimization_service,
    )

    # Execution orchestration boundary:
    # gate -> physical apply -> acceptance -> audit.
    monkeypatch.setattr(
        execution_orchestrator,
        "ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "AISuggestionRepository",
        FakeSuggestionRepository,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "IntelligenceExecutionGate",
        FakeExecutionGate,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "AISuggestionService",
        FakeAISuggestionService,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "IntelligenceEventRepository",
        FakeIntelligenceEventRepository,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "IntelligenceEventService",
        FakeIntelligenceEventService,
    )


@pytest.mark.asyncio
async def test_apply_reoptimization_executes_accepts_audits_and_commits(
    monkeypatch,
):
    optimization_service = FakeOptimizationService()

    patch_router_dependencies(
        monkeypatch,
        optimization_service=optimization_service,
    )

    session = FakeSession()
    current_user = SimpleNamespace(id=USER_ID)
    payload = build_payload()

    result = await intelligence_router.apply_reoptimization(
        payload=payload,
        current_user=current_user,
        session=session,
    )

    assert result.applied is True
    assert result.new_reservation_id == RESERVATION_ID
    assert result.new_reservation_primary_table_id == TABLE_ID

    assert len(FakeExecutionGate.calls) == 1
    gate_call = FakeExecutionGate.calls[0]

    assert gate_call["suggestion_id"] == SUGGESTION_ID
    assert gate_call["new_reservation_id"] == RESERVATION_ID
    assert gate_call["new_reservation_table_ids"] == [TABLE_ID]
    assert gate_call["new_reservation_primary_table_id"] == TABLE_ID
    assert gate_call["moves"] == []

    current_state = gate_call[
        "current_reservation_state"
    ]

    assert current_state == {
        "id": str(RESERVATION_ID),
        "party_size": 10,
        "reservation_time": (
            "2026-09-27T11:00:00+08:00"
        ),
        "duration_minutes": 90,
        "status": "pending",
        "primary_table_id": str(TABLE_ID),
        "table_ids": [
            str(TABLE_ID),
        ],
    }

    optimization_service.apply_reoptimization.assert_awaited_once_with(
        session=session,
        payload=payload,
        allowed_restaurant_ids=[RESTAURANT_ID],
    )

    assert FakeAISuggestionService.accept_calls == [
        {
            "suggestion_id": SUGGESTION_ID,
            "restaurant_ids": [RESTAURANT_ID],
            "source": IntelligenceEventSource.MANAGER,
        },
    ]

    assert len(FakeIntelligenceEventService.record_calls) == 1
    audit_call = FakeIntelligenceEventService.record_calls[0]

    assert audit_call["restaurant_id"] == RESTAURANT_ID
    assert audit_call["entity_type"] == "reservation"
    assert audit_call["entity_id"] == RESERVATION_ID
    assert audit_call["actor_user_id"] == USER_ID
    assert audit_call["payload"]["suggestion_id"] == str(SUGGESTION_ID)
    assert audit_call["payload"]["applied"] is True

    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_failure_does_not_accept_audit_or_commit(
    monkeypatch,
):
    optimization_service = FailingOptimizationService()

    patch_router_dependencies(
        monkeypatch,
        optimization_service=optimization_service,
    )

    session = FakeSession()
    current_user = SimpleNamespace(id=USER_ID)
    payload = build_payload()

    with pytest.raises(
        RuntimeError,
        match="apply failed",
    ):
        await intelligence_router.apply_reoptimization(
            payload=payload,
            current_user=current_user,
            session=session,
        )

    assert len(FakeExecutionGate.calls) == 1

    optimization_service.apply_reoptimization.assert_awaited_once_with(
        session=session,
        payload=payload,
        allowed_restaurant_ids=[RESTAURANT_ID],
    )

    assert FakeAISuggestionService.accept_calls == []
    assert FakeIntelligenceEventService.record_calls == []
    session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_autonomous_apply_uses_ai_source_without_manager_actor(
    monkeypatch,
):
    optimization_service = FakeOptimizationService()

    patch_router_dependencies(
        monkeypatch,
        optimization_service=optimization_service,
    )

    session = FakeSession()
    payload = build_payload()

    result = await execution_orchestrator.IntelligenceExecutionOrchestrator(
        intelligence_service=optimization_service,
    ).apply_reoptimization(
        session=session,
        payload=payload,
        allowed_restaurant_ids=[RESTAURANT_ID],
        source=IntelligenceEventSource.AI,
        actor_user_id=None,
    )

    assert result.applied is True

    assert FakeAISuggestionService.accept_calls == [
        {
            "suggestion_id": SUGGESTION_ID,
            "restaurant_ids": [RESTAURANT_ID],
            "source": IntelligenceEventSource.AI,
        },
    ]

    assert len(
        FakeIntelligenceEventService.record_calls
    ) == 1

    audit_call = (
        FakeIntelligenceEventService.record_calls[0]
    )

    assert (
        audit_call["source"]
        == IntelligenceEventSource.AI
    )
    assert audit_call["actor_user_id"] is None
    assert (
        audit_call["restaurant_id"]
        == RESTAURANT_ID
    )
    assert (
        audit_call["entity_id"]
        == RESERVATION_ID
    )

    session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_manager_apply_reoptimization_sends_confirmation_email(
    monkeypatch,
):
    optimization_service = FakeOptimizationService()

    patch_router_dependencies(
        monkeypatch,
        optimization_service=optimization_service,
    )

    FakeEmailService.confirmation_calls = []

    pending_reservation = SimpleNamespace(
        id=RESERVATION_ID,
        restaurant_id=RESTAURANT_ID,
        customer_name="Claudio Bisio",
        customer_email="claudio@example.com",
        reservation_time=datetime.fromisoformat(
            "2026-09-27T11:00:00+08:00"
        ),
        party_size=10,
        duration_minutes=90,
        language="it",
        status=ReservationStatus.PENDING,
    )

    confirmed_reservation = SimpleNamespace(
        id=RESERVATION_ID,
        restaurant_id=RESTAURANT_ID,
        customer_name="Claudio Bisio",
        customer_email="claudio@example.com",
        reservation_time=datetime.fromisoformat(
            "2026-09-27T11:00:00+08:00"
        ),
        party_size=10,
        duration_minutes=90,
        language="it",
        status=ReservationStatus.CONFIRMED,
    )

    restaurant = SimpleNamespace(
        id=RESTAURANT_ID,
        name="Perugino",
        subscription_status="active",
        timezone="Australia/Perth",
        preferred_language="it",
    )

    reservation_reads = 0

    async def get_reservation(*args, **kwargs):
        nonlocal reservation_reads
        reservation_reads += 1

        if reservation_reads == 1:
            return pending_reservation

        return confirmed_reservation

    async def get_restaurant(*args, **kwargs):
        return restaurant

    monkeypatch.setattr(
        intelligence_router,
        "EmailService",
        FakeEmailService,
        raising=False,
    )

    monkeypatch.setattr(
        intelligence_router.ReservationRepository,
        "get_by_id_for_restaurants",
        get_reservation,
        raising=False,
    )

    monkeypatch.setattr(
        intelligence_router.RestaurantRepository,
        "get_by_id",
        get_restaurant,
        raising=False,
    )

    session = FakeSession()
    current_user = SimpleNamespace(id=USER_ID)
    payload = build_payload()

    result = await intelligence_router.apply_reoptimization(
        payload=payload,
        current_user=current_user,
        session=session,
    )

    assert result.applied is True

    assert FakeEmailService.confirmation_calls == [
        {
            "to_email": "claudio@example.com",
            "restaurant_name": "Perugino",
            "customer_name": "Claudio Bisio",
            "reservation_id": str(RESERVATION_ID),
            "reservation_time": "27/09/2026 alle 11:00",
            "party_size": 10,
            "language": "it",
        }
    ]

@pytest.mark.asyncio
async def test_manager_apply_reoptimization_does_not_resend_confirmation_for_already_confirmed_reservation(
    monkeypatch,
):
    optimization_service = FakeOptimizationService()

    patch_router_dependencies(
        monkeypatch,
        optimization_service=optimization_service,
    )

    FakeEmailService.confirmation_calls = []

    confirmed_reservation = SimpleNamespace(
        id=RESERVATION_ID,
        restaurant_id=RESTAURANT_ID,
        customer_name="Claudio Bisio",
        customer_email="claudio@example.com",
        reservation_time=datetime.fromisoformat(
            "2026-09-27T11:00:00+08:00"
        ),
        party_size=10,
        duration_minutes=90,
        language="it",
        status=ReservationStatus.CONFIRMED,
    )

    async def get_reservation(*args, **kwargs):
        return confirmed_reservation

    monkeypatch.setattr(
        intelligence_router,
        "EmailService",
        FakeEmailService,
        raising=False,
    )

    monkeypatch.setattr(
        intelligence_router.ReservationRepository,
        "get_by_id_for_restaurants",
        get_reservation,
        raising=False,
    )

    session = FakeSession()
    current_user = SimpleNamespace(id=USER_ID)
    payload = build_payload()

    result = await intelligence_router.apply_reoptimization(
        payload=payload,
        current_user=current_user,
        session=session,
    )

    assert result.applied is True
    assert FakeEmailService.confirmation_calls == []

@pytest.mark.asyncio
async def test_stale_modification_gate_failure_stops_before_physical_apply(
    monkeypatch,
):
    optimization_service = FakeOptimizationService()

    patch_router_dependencies(
        monkeypatch,
        optimization_service=optimization_service,
    )

    FakeExecutionGate.error = ValidationError(
        "Modification reoptimization original reservation "
        "state is stale: party size changed."
    )

    session = FakeSession()
    current_user = SimpleNamespace(
        id=USER_ID,
    )
    payload = build_payload()

    with pytest.raises(
        ValidationError,
        match="original reservation state is stale",
    ):
        await intelligence_router.apply_reoptimization(
            payload=payload,
            current_user=current_user,
            session=session,
        )

    assert len(
        FakeExecutionGate.calls
    ) == 1

    optimization_service.apply_reoptimization.assert_not_awaited()

    assert (
        FakeAISuggestionService.accept_calls
        == []
    )

    assert (
        FakeIntelligenceEventService.record_calls
        == []
    )

    session.commit.assert_not_awaited()
class FakeLiveExecutionGate:
    calls = []

    def __init__(self, *, repository):
        self.repository = repository

    async def validate_live_seated_modification(
        self,
        **kwargs,
    ):
        self.__class__.calls.append(kwargs)


class FakeLiveReservationService:
    apply_calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def apply_live_seated_modification_for_restaurants(
        self,
        **kwargs,
    ):
        self.__class__.apply_calls.append(kwargs)

        return SimpleNamespace(
            id=RESERVATION_ID,
            restaurant_id=RESTAURANT_ID,
            party_size=4,
            reservation_time=datetime.fromisoformat(
                "2026-10-17T11:30:00+00:00"
            ),
            duration_minutes=90,
            status=ReservationStatus.SEATED,
            table_id=TABLE_ID,
            assigned_table_ids=[TABLE_ID],
            table_assignments=[],
        )


@pytest.mark.asyncio
async def test_apply_live_seated_modification_gates_mutates_accepts_and_audits(
    monkeypatch,
):
    original_table_id = uuid4()

    seated_reservation = SimpleNamespace(
        id=RESERVATION_ID,
        restaurant_id=RESTAURANT_ID,
        party_size=2,
        reservation_time=datetime.fromisoformat(
            "2026-10-17T11:30:00+00:00"
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
        table_assignments=[],
    )

    FakeReservationRepository.current_reservation = (
        seated_reservation
    )
    FakeSuggestionRepository.current_suggestion = SimpleNamespace(
        id=SUGGESTION_ID,
        restaurant_id=RESTAURANT_ID,
        reservation_id=RESERVATION_ID,
        payload={
            "requested_modification": {
                "party_size": 4,
                "reservation_time": (
                    "2026-10-17T11:30:00+00:00"
                ),
            },
        },
    )

    FakeLiveExecutionGate.calls = []
    FakeLiveReservationService.apply_calls = []
    FakeAISuggestionService.accept_calls = []
    FakeIntelligenceEventService.record_calls = []

    monkeypatch.setattr(
        execution_orchestrator,
        "ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "AISuggestionRepository",
        FakeSuggestionRepository,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "IntelligenceExecutionGate",
        FakeLiveExecutionGate,
    )
    monkeypatch.setattr(
        "app.services.reservation_service.ReservationService",
        FakeLiveReservationService,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "AISuggestionService",
        FakeAISuggestionService,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "IntelligenceEventRepository",
        FakeIntelligenceEventRepository,
    )
    monkeypatch.setattr(
        execution_orchestrator,
        "IntelligenceEventService",
        FakeIntelligenceEventService,
    )

    session = FakeSession()

    payload = (
        IntelligenceApplyLiveSeatedModificationRequest(
            suggestion_id=SUGGESTION_ID,
            reservation_id=RESERVATION_ID,
            destination_table_ids=[TABLE_ID],
            destination_primary_table_id=TABLE_ID,
        )
    )

    orchestrator = (
        execution_orchestrator
        .IntelligenceExecutionOrchestrator(
            intelligence_service=FakeOptimizationService(),
        )
    )

    result = await orchestrator.apply_live_seated_modification(
        session=session,
        payload=payload,
        allowed_restaurant_ids=[RESTAURANT_ID],
        source=IntelligenceEventSource.MANAGER,
        actor_user_id=USER_ID,
    )

    assert result.applied is True
    assert result.reservation_id == RESERVATION_ID
    assert result.restaurant_id == RESTAURANT_ID
    assert result.party_size == 4
    assert result.status == "seated"
    assert result.primary_table_id == TABLE_ID
    assert result.table_ids == [TABLE_ID]

    assert len(FakeLiveExecutionGate.calls) == 1

    gate_call = FakeLiveExecutionGate.calls[0]

    assert gate_call["suggestion_id"] == SUGGESTION_ID
    assert gate_call["reservation_id"] == RESERVATION_ID
    assert gate_call["destination_table_ids"] == [
        TABLE_ID
    ]
    assert (
        gate_call["destination_primary_table_id"]
        == TABLE_ID
    )

    assert gate_call["current_reservation_state"] == {
        "id": str(RESERVATION_ID),
        "party_size": 2,
        "reservation_time": (
            "2026-10-17T11:30:00+00:00"
        ),
        "duration_minutes": 90,
        "status": "seated",
        "primary_table_id": str(original_table_id),
        "table_ids": [str(original_table_id)],
    }

    assert FakeLiveReservationService.apply_calls == [
        {
            "reservation_id": RESERVATION_ID,
            "restaurant_ids": [RESTAURANT_ID],
            "requested_party_size": 4,
            "destination_table_ids": [TABLE_ID],
            "destination_primary_table_id": TABLE_ID,
        }
    ]

    assert FakeAISuggestionService.accept_calls == [
        {
            "suggestion_id": SUGGESTION_ID,
            "restaurant_ids": [RESTAURANT_ID],
            "source": IntelligenceEventSource.MANAGER,
        }
    ]

    assert len(
        FakeIntelligenceEventService.record_calls
    ) == 1

    audit_call = (
        FakeIntelligenceEventService.record_calls[0]
    )

    assert audit_call["restaurant_id"] == RESTAURANT_ID
    assert audit_call["entity_type"] == "reservation"
    assert audit_call["entity_id"] == RESERVATION_ID
    assert audit_call["source"] == (
        IntelligenceEventSource.MANAGER
    )
    assert audit_call["actor_user_id"] == USER_ID

    assert audit_call["payload"]["suggestion_id"] == str(
        SUGGESTION_ID
    )
    assert audit_call["payload"]["requested_party_size"] == 4
    assert audit_call["payload"]["from_table_ids"] == [
        str(original_table_id)
    ]
    assert audit_call["payload"]["to_table_ids"] == [
        str(TABLE_ID)
    ]
    assert audit_call["payload"]["status"] == "seated"

    session.commit.assert_not_awaited()



@pytest.mark.asyncio
async def test_apply_live_seated_modification_mutation_failure_does_not_accept_or_audit(
    monkeypatch,
):
    from types import SimpleNamespace
    from uuid import uuid4

    from app.core.exceptions import ConflictError
    from app.intelligence_execution.orchestrator import (
        IntelligenceExecutionOrchestrator,
    )
    from app.models.ai_suggestion import (
        AISuggestionStatus,
        AISuggestionType,
    )
    from app.models.reservation import ReservationStatus

    suggestion_id = uuid4()
    expected_suggestion_id = suggestion_id
    reservation_id = uuid4()
    expected_reservation_id = reservation_id
    restaurant_id = uuid4()
    original_table_id = uuid4()
    destination_table_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        party_size=2,
        reservation_time=datetime.fromisoformat(
            "2026-10-17T11:30:00+00:00"
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
        table_assignments=[],
        table=SimpleNamespace(
            id=original_table_id,
            table_number="43",
        ),
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        suggestion_type=(
            AISuggestionType.LIVE_SEATED_MODIFICATION
        ),
        status=AISuggestionStatus.PENDING,
        expires_at=None,
        payload={
            "reservation": {
                "id": str(reservation_id),
                "party_size": 2,
                "reservation_time": (
                    "2026-10-17T11:30:00+00:00"
                ),
                "duration_minutes": 90,
                "status": "seated",
                "primary_table_id": str(original_table_id),
                "table_ids": [
                    str(original_table_id),
                ],
            },
            "requested_modification": {
                "party_size": 4,
                "reservation_time": (
                    "2026-10-17T11:30:00+00:00"
                ),
            },
            "plan": {
                "new_reservation_assignment": {
                    "table_ids": [
                        str(destination_table_id),
                    ],
                },
                "moves": [],
                "moved_reservations_count": 0,
            },
        },
    )

    class FakeReservationRepository:
        def __init__(self, db):
            self.db = db

        async def get_by_id_for_restaurants(
            self,
            reservation_id: object,
            restaurant_ids,
        ):
            assert reservation_id == expected_reservation_id
            assert restaurant_ids == [restaurant_id]
            return reservation

    class FakeSuggestionRepository:
        def __init__(self, db):
            self.db = db

        async def get_by_id(
            self,
            suggestion_id: object,
            *,
            restaurant_ids=None,
        ):
            assert suggestion_id == expected_suggestion_id
            assert restaurant_ids == [restaurant_id]
            return suggestion

    class FakeLiveExecutionGate:
        async def validate_live_seated_modification(
            self,
            **kwargs,
        ):
            return suggestion

    class FakeLiveReservationService:
        def __init__(self, **kwargs):
            pass

        async def apply_live_seated_modification_for_restaurants(
            self,
            **kwargs,
        ):
            raise ConflictError(
                "Destination became occupied."
            )

    accept_calls = []
    audit_calls = []

    async def fake_accept(*args, **kwargs):
        accept_calls.append(
            {
                "args": args,
                "kwargs": kwargs,
            }
        )

    class FakeIntelligenceEventRepository:
        def __init__(self, db):
            self.db = db

    class FakeIntelligenceEventService:
        def __init__(self, repository):
            self.repository = repository

        async def record(self, **kwargs):
            audit_calls.append(dict(kwargs))

    monkeypatch.setattr(
        "app.intelligence_execution.orchestrator.ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        "app.intelligence_execution.orchestrator.AISuggestionRepository",
        FakeSuggestionRepository,
    )
    monkeypatch.setattr(
        "app.services.reservation_service.ReservationService",
        FakeLiveReservationService,
    )
    monkeypatch.setattr(
        "app.intelligence_execution.orchestrator.AISuggestionService.accept",
        fake_accept,
    )
    monkeypatch.setattr(
        "app.intelligence_execution.orchestrator.IntelligenceEventRepository",
        FakeIntelligenceEventRepository,
    )
    monkeypatch.setattr(
        "app.intelligence_execution.orchestrator.IntelligenceEventService",
        FakeIntelligenceEventService,
    )

    orchestrator = IntelligenceExecutionOrchestrator(
        intelligence_service=SimpleNamespace(),
    )
    orchestrator.execution_gate = FakeLiveExecutionGate()

    from app.intelligence.schemas import (
        IntelligenceApplyLiveSeatedModificationRequest,
    )
    from app.intelligence_events.models import (
        IntelligenceEventSource,
    )

    session = SimpleNamespace()

    payload = IntelligenceApplyLiveSeatedModificationRequest(
        suggestion_id=suggestion_id,
        reservation_id=reservation_id,
        destination_table_ids=[
            destination_table_id,
        ],
        destination_primary_table_id=(
            destination_table_id
        ),
    )

    with pytest.raises(
        ConflictError,
        match="Destination became occupied",
    ):
        await orchestrator.apply_live_seated_modification(
            session=session,
            payload=payload,
            allowed_restaurant_ids=[
                restaurant_id,
            ],
            source=IntelligenceEventSource.MANAGER,
            actor_user_id=None,
        )

    assert accept_calls == []
    assert audit_calls == []
    assert suggestion.status == AISuggestionStatus.PENDING


@pytest.mark.asyncio
async def test_manager_apply_live_seated_modification_calls_orchestrator_and_commits(
    monkeypatch,
):
    destination_table_id = uuid4()

    payload = IntelligenceApplyLiveSeatedModificationRequest(
        suggestion_id=SUGGESTION_ID,
        reservation_id=RESERVATION_ID,
        destination_table_ids=[destination_table_id],
        destination_primary_table_id=destination_table_id,
    )

    expected_result = SimpleNamespace(
        reservation_id=RESERVATION_ID,
        restaurant_id=RESTAURANT_ID,
        party_size=4,
        primary_table_id=destination_table_id,
        table_ids=[destination_table_id],
        table_numbers=["50"],
        status="seated",
        mode="assisted_live_service",
        applied=True,
    )

    class FakeLiveRouterOrchestrator:
        calls = []

        def __init__(self, *, intelligence_service):
            self.intelligence_service = intelligence_service

        async def apply_live_seated_modification(self, **kwargs):
            self.__class__.calls.append(kwargs)
            return expected_result

    monkeypatch.setattr(
        intelligence_router,
        "RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        intelligence_router,
        "IntelligenceExecutionOrchestrator",
        FakeLiveRouterOrchestrator,
    )

    session = FakeSession()
    current_user = SimpleNamespace(id=USER_ID)

    result = await intelligence_router.apply_live_seated_modification(
        payload=payload,
        current_user=current_user,
        session=session,
    )

    assert result is expected_result
    assert FakeLiveRouterOrchestrator.calls == [
        {
            "session": session,
            "payload": payload,
            "allowed_restaurant_ids": [RESTAURANT_ID],
            "source": IntelligenceEventSource.MANAGER,
            "actor_user_id": USER_ID,
        },
    ]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_manager_apply_live_seated_modification_failure_does_not_commit(
    monkeypatch,
):
    destination_table_id = uuid4()

    payload = IntelligenceApplyLiveSeatedModificationRequest(
        suggestion_id=SUGGESTION_ID,
        reservation_id=RESERVATION_ID,
        destination_table_ids=[destination_table_id],
        destination_primary_table_id=destination_table_id,
    )

    class FailingLiveRouterOrchestrator:
        calls = []

        def __init__(self, *, intelligence_service):
            self.intelligence_service = intelligence_service

        async def apply_live_seated_modification(self, **kwargs):
            self.__class__.calls.append(kwargs)
            raise RuntimeError("live apply failed")

    monkeypatch.setattr(
        intelligence_router,
        "RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        intelligence_router,
        "IntelligenceExecutionOrchestrator",
        FailingLiveRouterOrchestrator,
    )

    session = FakeSession()
    current_user = SimpleNamespace(id=USER_ID)

    with pytest.raises(
        RuntimeError,
        match="live apply failed",
    ):
        await intelligence_router.apply_live_seated_modification(
            payload=payload,
            current_user=current_user,
            session=session,
        )

    assert FailingLiveRouterOrchestrator.calls == [
        {
            "session": session,
            "payload": payload,
            "allowed_restaurant_ids": [RESTAURANT_ID],
            "source": IntelligenceEventSource.MANAGER,
            "actor_user_id": USER_ID,
        },
    ]

    session.commit.assert_not_awaited()
