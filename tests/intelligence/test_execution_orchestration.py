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

import pytest

import app.intelligence.router as intelligence_router

from app.models.reservation import ReservationStatus
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
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
    def __init__(self, session):
        self.session = session

    async def get_by_id_for_restaurants(
        self,
        *,
        reservation_id,
        restaurant_ids,
    ):
        if (
            reservation_id == RESERVATION_ID
            and RESTAURANT_ID in restaurant_ids
        ):
            return SimpleNamespace(
                id=RESERVATION_ID,
                restaurant_id=RESTAURANT_ID,
                status=ReservationStatus.PENDING,
                customer_email=None,
            )

        return None


class FakeSuggestionRepository:
    def __init__(self, session):
        self.session = session


class FakeExecutionGate:
    calls = []

    def __init__(self, *, repository):
        self.repository = repository

    async def validate_reoptimization(self, **kwargs):
        self.__class__.calls.append(kwargs)


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