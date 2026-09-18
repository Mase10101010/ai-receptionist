from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import app.services.reservation_service as reservation_service_module
from app.intelligence_events.models import IntelligenceEventSource
from app.models.reservation import ReservationStatus
from app.services.reservation_service import ReservationService


class FakeNestedTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeSession:
    def begin_nested(self):
        return FakeNestedTransaction()


class FakeReservationRepository:
    def __init__(self, confirmed_reservation):
        self.db = FakeSession()
        self.confirmed_reservation = confirmed_reservation
        self.get_by_id_for_restaurants = AsyncMock(
            return_value=confirmed_reservation,
        )


class FakeRestaurantRepository:
    def __init__(self, restaurant):
        self.restaurant = restaurant

    async def get_by_id(self, restaurant_id):
        return self.restaurant


class FakeAuthority:
    calls = []

    def can_execute_stored_plan_automatically(
        self,
        *,
        plan,
        autopilot_enabled,
        temporal_context,
    ):
        self.calls.append(
            {
                "plan": plan,
                "autopilot_enabled": autopilot_enabled,
                "temporal_context": temporal_context,
            }
        )

        return SimpleNamespace(
            allowed=autopilot_enabled,
        )


class FakeMapper:
    calls = []

    def build_apply_request(
        self,
        *,
        suggestion,
    ):
        self.__class__.calls.append(
            suggestion
        )

        return SimpleNamespace(
            suggestion_id=suggestion.id,
        )


class FakeOrchestrator:
    calls = []

    def __init__(
        self,
        *,
        intelligence_service=None,
    ):
        self.intelligence_service = intelligence_service

    async def apply_reoptimization(
        self,
        **kwargs,
    ):
        self.__class__.calls.append(kwargs)

        return SimpleNamespace(
            applied=True,
        )


@pytest.mark.asyncio
async def test_eligible_opted_in_booking_executes_as_ai(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    confirmed_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=True,
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        payload={
            "plan": {
                "execution_eligibility": {
                    "eligibility": (
                        "eligible_for_automatic_execution"
                    ),
                },
            },
            "temporal_autopilot_safety": {
                "schema_version": (
                    "temporal_autopilot_safety.v1"
                ),
                "context": {
                    "calibration_state": (
                        "well_calibrated"
                    ),
                    "expected_turn_confidence": (
                        "high"
                    ),
                    "marginal_capacity_loss_ratio": 0.0,
                    "lost_future_available_slots": 0,
                },
            },
        },
    )

    repository = FakeReservationRepository(
        confirmed_reservation,
    )

    intelligence_service = SimpleNamespace()

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=intelligence_service,
    )

    FakeAuthority.calls = []
    FakeMapper.calls = []
    FakeOrchestrator.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "TemporalAutopilotAuthorityService",
        FakeAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is confirmed_reservation
    assert result.status == ReservationStatus.CONFIRMED

    assert len(FakeAuthority.calls) == 1

    authority_call = FakeAuthority.calls[0]

    assert authority_call["plan"] == suggestion.payload["plan"]
    assert authority_call["autopilot_enabled"] is True

    temporal_context = authority_call["temporal_context"]

    assert temporal_context is not None
    assert (
        temporal_context.calibration_state.value
        == "well_calibrated"
    )
    assert (
        temporal_context.expected_turn_confidence.value
        == "high"
    )
    assert temporal_context.marginal_capacity_loss_ratio == 0.0
    assert temporal_context.lost_future_available_slots == 0

    assert FakeMapper.calls == [
        suggestion,
    ]

    assert len(FakeOrchestrator.calls) == 1

    execution_call = FakeOrchestrator.calls[0]

    assert execution_call["session"] is repository.db
    assert execution_call["allowed_restaurant_ids"] == [
        restaurant_id
    ]
    assert (
        execution_call["source"]
        == IntelligenceEventSource.AI
    )
    assert execution_call["actor_user_id"] is None

    repository.get_by_id_for_restaurants.assert_awaited_once_with(
        reservation_id=reservation_id,
        restaurant_ids=[restaurant_id],
    )

@pytest.mark.asyncio
async def test_autopilot_does_not_execute_when_authority_denies(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=False,
    )

    suggestion = SimpleNamespace(
        id=uuid4(),
        payload={
            "plan": {
                "execution_eligibility": {},
            },
        },
    )

    repository = FakeReservationRepository(
        pending_reservation,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    class DenyingAuthority:
        def can_execute_stored_plan_automatically(
            self,
            *,
            plan,
            autopilot_enabled,
        ):
            return False

    FakeMapper.calls = []
    FakeOrchestrator.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotAuthorityService",
        DenyingAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is pending_reservation
    assert result.status == ReservationStatus.PENDING

    assert FakeMapper.calls == []
    assert FakeOrchestrator.calls == []

    repository.get_by_id_for_restaurants.assert_not_awaited()


@pytest.mark.asyncio
async def test_autopilot_failure_returns_pending_and_does_not_escape(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=True,
    )

    suggestion = SimpleNamespace(
        id=uuid4(),
        payload={
            "plan": {
                "execution_eligibility": {
                    "eligibility": (
                        "eligible_for_automatic_execution"
                    ),
                },
            },
        },
    )

    repository = FakeReservationRepository(
        pending_reservation,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    class AllowingAuthority:
        def can_execute_stored_plan_automatically(
            self,
            *,
            plan,
            autopilot_enabled,
        ):
            return True

    class FailingOrchestrator:
        async def apply_reoptimization(
            self,
            **kwargs,
        ):
            raise RuntimeError(
                "autopilot execution failed"
            )

        def __init__(
            self,
            *,
            intelligence_service=None,
        ):
            pass

    FakeMapper.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotAuthorityService",
        AllowingAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FailingOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is pending_reservation
    assert result.status == ReservationStatus.PENDING

    repository.get_by_id_for_restaurants.assert_not_awaited()

@pytest.mark.asyncio
async def test_missing_temporal_evidence_fails_closed(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=True,
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        payload={
            "plan": {
                "execution_eligibility": {
                    "eligibility": (
                        "eligible_for_automatic_execution"
                    ),
                },
            },
        },
    )

    repository = FakeReservationRepository(
        pending_reservation,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    class FakeTemporalAuthority:
        calls = []

        def can_execute_stored_plan_automatically(
            self,
            *,
            plan,
            autopilot_enabled,
            temporal_context,
        ):
            self.calls.append(
                {
                    "plan": plan,
                    "autopilot_enabled": autopilot_enabled,
                    "temporal_context": temporal_context,
                }
            )

            return SimpleNamespace(
                allowed=False,
            )

    FakeMapper.calls = []
    FakeOrchestrator.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "TemporalAutopilotAuthorityService",
        FakeTemporalAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is pending_reservation
    assert result.status == ReservationStatus.PENDING

    assert len(FakeTemporalAuthority.calls) == 1

    authority_call = FakeTemporalAuthority.calls[0]

    assert authority_call["autopilot_enabled"] is True
    assert authority_call["temporal_context"] is None

    assert FakeMapper.calls == []
    assert FakeOrchestrator.calls == []

@pytest.mark.asyncio
async def test_unsafe_temporal_evidence_blocks_execution(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=True,
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        payload={
            "plan": {
                "execution_eligibility": {
                    "eligibility": (
                        "eligible_for_automatic_execution"
                    ),
                },
            },
            "temporal_autopilot_safety": {
                "schema_version": (
                    "temporal_autopilot_safety.v1"
                ),
                "context": {
                    "calibration_state": (
                        "well_calibrated"
                    ),
                    "expected_turn_confidence": (
                        "high"
                    ),
                    "marginal_capacity_loss_ratio": 0.25,
                    "lost_future_available_slots": 1,
                },
            },
        },
    )

    repository = FakeReservationRepository(
        pending_reservation,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    class FakeTemporalAuthority:
        calls = []

        def can_execute_stored_plan_automatically(
            self,
            *,
            plan,
            autopilot_enabled,
            temporal_context,
        ):
            self.calls.append(
                {
                    "plan": plan,
                    "autopilot_enabled": autopilot_enabled,
                    "temporal_context": temporal_context,
                }
            )

            return SimpleNamespace(
                allowed=False,
            )

    FakeMapper.calls = []
    FakeOrchestrator.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "TemporalAutopilotAuthorityService",
        FakeTemporalAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is pending_reservation
    assert result.status == ReservationStatus.PENDING

    assert len(FakeTemporalAuthority.calls) == 1

    temporal_context = (
        FakeTemporalAuthority
        .calls[0]["temporal_context"]
    )

    assert temporal_context is not None
    assert (
        temporal_context.marginal_capacity_loss_ratio
        == 0.25
    )
    assert (
        temporal_context.lost_future_available_slots
        == 1
    )

    assert FakeMapper.calls == []
    assert FakeOrchestrator.calls == []

@pytest.mark.asyncio
async def test_temporal_authority_failure_fails_closed(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=True,
    )

    suggestion = SimpleNamespace(
        id=uuid4(),
        payload={
            "plan": {
                "execution_eligibility": {
                    "eligibility": (
                        "eligible_for_automatic_execution"
                    ),
                },
            },
            "temporal_autopilot_safety": {
                "schema_version": (
                    "temporal_autopilot_safety.v1"
                ),
                "context": {
                    "calibration_state": (
                        "well_calibrated"
                    ),
                    "expected_turn_confidence": (
                        "high"
                    ),
                    "marginal_capacity_loss_ratio": 0.0,
                    "lost_future_available_slots": 0,
                },
            },
        },
    )

    repository = FakeReservationRepository(
        pending_reservation,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    class FailingTemporalAuthority:
        def can_execute_stored_plan_automatically(
            self,
            *,
            plan,
            autopilot_enabled,
            temporal_context,
        ):
            raise RuntimeError(
                "temporal authority failure"
            )

    FakeMapper.calls = []
    FakeOrchestrator.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "TemporalAutopilotAuthorityService",
        FailingTemporalAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is pending_reservation
    assert result.status == ReservationStatus.PENDING

    assert FakeMapper.calls == []
    assert FakeOrchestrator.calls == []

@pytest.mark.asyncio
async def test_unknown_temporal_evidence_version_fails_closed(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        autopilot_enabled=True,
    )

    suggestion = SimpleNamespace(
        id=uuid4(),
        payload={
            "plan": {
                "execution_eligibility": {
                    "eligibility": (
                        "eligible_for_automatic_execution"
                    ),
                },
            },
            "temporal_autopilot_safety": {
                "schema_version": (
                    "temporal_autopilot_safety.v999"
                ),
                "context": {
                    "calibration_state": (
                        "well_calibrated"
                    ),
                    "expected_turn_confidence": (
                        "high"
                    ),
                    "marginal_capacity_loss_ratio": 0.0,
                    "lost_future_available_slots": 0,
                },
            },
        },
    )

    repository = FakeReservationRepository(
        pending_reservation,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(
            restaurant
        ),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    class FakeTemporalAuthority:
        calls = []

        def can_execute_stored_plan_automatically(
            self,
            *,
            plan,
            autopilot_enabled,
            temporal_context,
        ):
            self.calls.append(
                {
                    "plan": plan,
                    "autopilot_enabled": autopilot_enabled,
                    "temporal_context": temporal_context,
                }
            )

            return SimpleNamespace(
                allowed=False,
            )

    FakeMapper.calls = []
    FakeOrchestrator.calls = []

    monkeypatch.setattr(
        reservation_service_module,
        "TemporalAutopilotAuthorityService",
        FakeTemporalAuthority,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "AutopilotReoptimizationMapper",
        FakeMapper,
    )

    monkeypatch.setattr(
        reservation_service_module,
        "IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )

    result = await service._try_autopilot_reoptimization(
        reservation=pending_reservation,
        suggestion=suggestion,
    )

    assert result is pending_reservation
    assert result.status == ReservationStatus.PENDING

    assert len(FakeTemporalAuthority.calls) == 1
    assert (
        FakeTemporalAuthority
        .calls[0]["temporal_context"]
        is None
    )

    assert FakeMapper.calls == []
    assert FakeOrchestrator.calls == []