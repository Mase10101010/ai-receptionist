from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.intelligence.schemas import (
    IntelligenceReoptimizeRequest,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)
from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    ReoptimizationPlan,
    ReoptimizationResult,
    ScoredAssignment,
)
from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotSafetyContext,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)
from app.models.reservation import (
    Reservation,
    ReservationStatus,
)
from app.models.service_area import ServiceArea
from app.models.table import Table


NOW = datetime(
    2026,
    9,
    8,
    19,
    0,
    tzinfo=timezone.utc,
)


class FakeReoptimizer:
    def __init__(
        self,
        *,
        plan: ReoptimizationPlan,
    ) -> None:
        self.plan = plan
        self.calls = []

    def reoptimize(
        self,
        **kwargs,
    ) -> ReoptimizationResult:
        self.calls.append(kwargs)

        return ReoptimizationResult(
            available=True,
            recommended=self.plan,
            alternatives=(),
            evaluated_plans=1,
            rejected_plans=0,
        )


class RecordingLearningSnapshotService:
    def __init__(self) -> None:
        self.calls = []
        self.snapshot = object()

    async def build(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)
        return self.snapshot


class RecordingCalibrationSnapshotService:
    def __init__(self) -> None:
        self.calls = []
        self.assessment = object()

    async def build(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)

        return SimpleNamespace(
            assessment=self.assessment,
        )


class RecordingSafetyResolver:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.calls = []
        self.fail = fail

    def resolve(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)

        if self.fail:
            raise RuntimeError(
                "Temporal safety unavailable"
            )

        return SimpleNamespace(
            context=TemporalAutopilotSafetyContext(
                calibration_state=(
                    TemporalCalibrationState
                    .WELL_CALIBRATED
                ),
                expected_turn_confidence=(
                    ExpectedTurnConfidence.HIGH
                ),
                marginal_capacity_loss_ratio=0.0,
                lost_future_available_slots=0,
            )
        )


class FakeCalibrationMetricsService:
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        pass

    async def calculate(
        self,
        **kwargs,
    ):
        return SimpleNamespace()


def _build_plan(
    *,
    table_id,
) -> ReoptimizationPlan:
    assignment = ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(table_id),
            table_ids=(
                str(table_id),
            ),
            start_at=NOW,
            end_at=(
                NOW
                + timedelta(minutes=90)
            ),
            capacity=4,
            minimum_capacity=1,
            area_id=None,
            floor_id=None,
        ),
        score=90.0,
        seat_waste=0,
        fragmentation_minutes=0,
        explanation="Technical assignment.",
    )

    return ReoptimizationPlan(
        new_reservation_assignment=assignment,
        moves=(),
        score=90.0,
        total_seat_waste=0,
        moved_reservations_count=0,
        explanation="Technical plan.",
    )


async def _seed_table_and_baseline(
    db_session,
):
    restaurant_id = uuid4()

    service_area = ServiceArea(
        restaurant_id=restaurant_id,
        name="Main",
        area_type="indoor",
        is_active=True,
    )

    db_session.add(service_area)
    await db_session.flush()

    table = Table(
        restaurant_id=restaurant_id,
        service_area_id=service_area.id,
        table_code="T1",
        table_number="1",
        seats=4,
        is_active=True,
    )

    db_session.add(table)
    await db_session.flush()

    baseline_reservation = Reservation(
        restaurant_id=restaurant_id,
        table_id=table.id,
        customer_name="Existing Guest",
        customer_phone="+390000000000",
        customer_email="existing@example.com",
        party_size=2,
        reservation_time=NOW,
        duration_minutes=90,
        status=ReservationStatus.CONFIRMED,
    )

    db_session.add(baseline_reservation)
    await db_session.flush()

    return (
        restaurant_id,
        table,
        baseline_reservation,
    )


def _service(
    *,
    plan,
    learning_service,
    calibration_service,
    resolver,
):
    service = IntelligenceOptimizationService(
        reoptimizer=FakeReoptimizer(
            plan=plan,
        ),
        temporal_learning_snapshot_service=(
            learning_service
        ),
        temporal_calibration_snapshot_service=(
            calibration_service
        ),
        temporal_reoptimization_safety_resolver=(
            resolver
        ),
    )

    async def no_recommendation_context(
        **kwargs,
    ):
        return None, None

    service._build_recommendation_context = (
        no_recommendation_context
    )

    return service


def _payload(
    *,
    restaurant_id,
    reservation_id=None,
):
    return IntelligenceReoptimizeRequest(
        restaurant_id=restaurant_id,
        requested_start=NOW,
        party_size=4,
        duration_minutes=90,
        reservation_id=reservation_id,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        preferred_service_area_id=None,
        max_reservations_to_move=1,
        max_plans=5,
    )


@pytest.mark.asyncio
async def test_temporal_safety_is_exposed_on_reoptimization_plan(
    db_session,
    monkeypatch,
):
    (
        restaurant_id,
        table,
        _,
    ) = await _seed_table_and_baseline(
        db_session
    )

    target_reservation_id = uuid4()

    learning = (
        RecordingLearningSnapshotService()
    )

    calibration = (
        RecordingCalibrationSnapshotService()
    )

    resolver = RecordingSafetyResolver()

    monkeypatch.setattr(
        "app.intelligence.sqlalchemy_service."
        "IntelligenceCalibrationMetricsService",
        FakeCalibrationMetricsService,
    )

    result = await _service(
        plan=_build_plan(
            table_id=table.id,
        ),
        learning_service=learning,
        calibration_service=calibration,
        resolver=resolver,
    ).reoptimize(
        session=db_session,
        payload=_payload(
            restaurant_id=restaurant_id,
            reservation_id=(
                target_reservation_id
            ),
        ),
    )

    assert result.available is True
    assert result.recommended is not None

    safety = (
        result.recommended
        .temporal_autopilot_safety
    )

    assert safety is not None

    assert (
        safety.calibration_state
        == "well_calibrated"
    )

    assert (
        safety.expected_turn_confidence
        == "high"
    )

    assert (
        safety.marginal_capacity_loss_ratio
        == 0.0
    )

    assert (
        safety.lost_future_available_slots
        == 0
    )


@pytest.mark.asyncio
async def test_temporal_resolver_receives_raw_plan_and_existing_baseline(
    db_session,
    monkeypatch,
):
    (
        restaurant_id,
        table,
        baseline_reservation,
    ) = await _seed_table_and_baseline(
        db_session
    )

    target_reservation_id = uuid4()
    plan = _build_plan(
        table_id=table.id,
    )

    learning = (
        RecordingLearningSnapshotService()
    )

    calibration = (
        RecordingCalibrationSnapshotService()
    )

    resolver = RecordingSafetyResolver()

    monkeypatch.setattr(
        "app.intelligence.sqlalchemy_service."
        "IntelligenceCalibrationMetricsService",
        FakeCalibrationMetricsService,
    )

    await _service(
        plan=plan,
        learning_service=learning,
        calibration_service=calibration,
        resolver=resolver,
    ).reoptimize(
        session=db_session,
        payload=_payload(
            restaurant_id=restaurant_id,
            reservation_id=(
                target_reservation_id
            ),
        ),
    )

    assert len(resolver.calls) == 1

    call = resolver.calls[0]

    assert call["plan"] is plan

    assert (
        call["new_reservation_id"]
        == target_reservation_id
    )

    assert (
        call["new_reservation_party_size"]
        == 4
    )

    assert (
        call["learning_snapshot"]
        is learning.snapshot
    )

    assert (
        call["calibration"]
        is calibration.assessment
    )

    reservations = call[
        "reservations"
    ]

    assert len(reservations) == 1

    assert (
        reservations[0].id
        == str(
            baseline_reservation.id
        )
    )

    assert (
        str(table.id)
        in reservations[0].table_ids
    )


@pytest.mark.asyncio
async def test_temporal_snapshots_are_built_once_per_reoptimize(
    db_session,
    monkeypatch,
):
    (
        restaurant_id,
        table,
        _,
    ) = await _seed_table_and_baseline(
        db_session
    )

    learning = (
        RecordingLearningSnapshotService()
    )

    calibration = (
        RecordingCalibrationSnapshotService()
    )

    resolver = RecordingSafetyResolver()

    monkeypatch.setattr(
        "app.intelligence.sqlalchemy_service."
        "IntelligenceCalibrationMetricsService",
        FakeCalibrationMetricsService,
    )

    await _service(
        plan=_build_plan(
            table_id=table.id,
        ),
        learning_service=learning,
        calibration_service=calibration,
        resolver=resolver,
    ).reoptimize(
        session=db_session,
        payload=_payload(
            restaurant_id=restaurant_id,
            reservation_id=uuid4(),
        ),
    )

    assert len(learning.calls) == 1
    assert len(calibration.calls) == 1

    assert (
        learning.calls[0][
            "restaurant_id"
        ]
        == restaurant_id
    )

    assert (
        calibration.calls[0][
            "restaurant_id"
        ]
        == restaurant_id
    )


@pytest.mark.asyncio
async def test_temporal_resolution_failure_preserves_reoptimization_response(
    db_session,
    monkeypatch,
):
    (
        restaurant_id,
        table,
        _,
    ) = await _seed_table_and_baseline(
        db_session
    )

    monkeypatch.setattr(
        "app.intelligence.sqlalchemy_service."
        "IntelligenceCalibrationMetricsService",
        FakeCalibrationMetricsService,
    )

    result = await _service(
        plan=_build_plan(
            table_id=table.id,
        ),
        learning_service=(
            RecordingLearningSnapshotService()
        ),
        calibration_service=(
            RecordingCalibrationSnapshotService()
        ),
        resolver=RecordingSafetyResolver(
            fail=True,
        ),
    ).reoptimize(
        session=db_session,
        payload=_payload(
            restaurant_id=restaurant_id,
            reservation_id=uuid4(),
        ),
    )

    assert result.available is True
    assert result.recommended is not None

    assert (
        result.recommended
        .temporal_autopilot_safety
        is None
    )

    assert (
        result.recommended.base_score
        == 90.0
    )


@pytest.mark.asyncio
async def test_missing_reservation_id_does_not_expose_temporal_autopilot_safety(
    db_session,
    monkeypatch,
):
    (
        restaurant_id,
        table,
        _,
    ) = await _seed_table_and_baseline(
        db_session
    )

    resolver = RecordingSafetyResolver()

    monkeypatch.setattr(
        "app.intelligence.sqlalchemy_service."
        "IntelligenceCalibrationMetricsService",
        FakeCalibrationMetricsService,
    )

    result = await _service(
        plan=_build_plan(
            table_id=table.id,
        ),
        learning_service=(
            RecordingLearningSnapshotService()
        ),
        calibration_service=(
            RecordingCalibrationSnapshotService()
        ),
        resolver=resolver,
    ).reoptimize(
        session=db_session,
        payload=_payload(
            restaurant_id=restaurant_id,
            reservation_id=None,
        ),
    )

    assert result.available is True
    assert result.recommended is not None

    assert (
        result.recommended
        .temporal_autopilot_safety
        is None
    )

    assert resolver.calls == []