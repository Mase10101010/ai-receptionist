from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from uuid import uuid4

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    IntelligenceTable,
    ReoptimizationPlan,
    ScoredAssignment,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.learning import (
    PartySizeTurnProfile,
    TemporalSampleState,
)
from app.intelligence_temporal.reoptimization_capacity_runner import (
    TemporalReoptimizationCapacityRun,
)
from app.intelligence_temporal.reoptimization_safety_resolver import (
    TemporalReoptimizationSafetyResolver,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)
from app.intelligence_temporal.snapshot import (
    TemporalLearningSnapshot,
)


NOW = datetime(
    2026,
    9,
    8,
    19,
    0,
    tzinfo=timezone.utc,
)

RESTAURANT_ID = uuid4()
NEW_RESERVATION_ID = uuid4()
TABLE_ID = str(uuid4())


def _table():
    return IntelligenceTable(
        id=TABLE_ID,
        table_number="1",
        min_capacity=1,
        max_capacity=4,
    )


def _plan():
    return ReoptimizationPlan(
        new_reservation_assignment=(
            ScoredAssignment(
                candidate=CandidateAssignment(
                    kind=(
                        AssignmentKind.SINGLE_TABLE
                    ),
                    resource_id=TABLE_ID,
                    table_ids=(TABLE_ID,),
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
                explanation="Candidate.",
            )
        ),
        moves=(),
        score=90.0,
        total_seat_waste=0,
        moved_reservations_count=0,
        explanation="Plan.",
    )


def _request():
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=4,
        duration_minutes=90,
        horizon_minutes=60,
        slot_minutes=30,
    )


def _profile(
    availability,
):
    slots = []

    for index, available in enumerate(
        availability
    ):
        start_at = (
            NOW
            + timedelta(
                minutes=index * 30
            )
        )

        slots.append(
            FutureCapacitySlot(
                start_at=start_at,
                end_at=(
                    start_at
                    + timedelta(minutes=90)
                ),
                directly_available=available,
            )
        )

    available_count = sum(
        1
        for slot in slots
        if slot.directly_available
    )

    return FutureCapacityResponse(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=4,
        duration_minutes=90,
        horizon_minutes=60,
        slot_minutes=30,
        slots=slots,
        summary=FutureCapacitySummary(
            total_slots=len(slots),
            directly_available_slots=(
                available_count
            ),
            unavailable_slots=(
                len(slots) - available_count
            ),
            availability_ratio=(
                available_count / len(slots)
                if slots
                else 0.0
            ),
            first_directly_available_at=next(
                (
                    slot.start_at
                    for slot in slots
                    if slot.directly_available
                ),
                None,
            ),
            longest_directly_available_run=(
                available_count
            ),
        ),
    )


def _snapshot():
    return TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=40,
        party_size_profiles=[
            PartySizeTurnProfile(
                restaurant_id=RESTAURANT_ID,
                party_size=4,
                sample_count=40,
                included_sample_count=40,
                excluded_outlier_count=0,
                sample_state=(
                    TemporalSampleState.ESTABLISHED
                ),
                mean_actual_dining_minutes=100.0,
                median_actual_dining_minutes=100.0,
                mean_planned_duration_minutes=90.0,
                mean_duration_delta_minutes=10.0,
                min_actual_dining_minutes=80,
                max_actual_dining_minutes=120,
            )
        ],
    )


def _calibration(
    state=TemporalCalibrationState.WELL_CALIBRATED,
):
    return SimpleNamespace(
        state=state,
    )


class RecordingCapacityRunner:
    def __init__(
        self,
        *,
        baseline=None,
        candidate=None,
    ):
        self.calls = []

        self.baseline = (
            baseline
            or _profile(
                [True, True, True]
            )
        )

        self.candidate = (
            candidate
            or _profile(
                [True, True, True]
            )
        )

    def run(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)

        return TemporalReoptimizationCapacityRun(
            baseline=self.baseline,
            candidate=self.candidate,
            new_reservation_id=(
                kwargs[
                    "new_reservation_id"
                ]
            ),
            moved_reservation_ids=(),
        )


def test_resolver_calls_capacity_runner_with_exact_inputs():
    runner = RecordingCapacityRunner()

    plan = _plan()
    request = _request()
    tables = [_table()]

    resolver = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=runner,
        )
    )

    resolver.resolve(
        plan=plan,
        new_reservation_id=(
            NEW_RESERVATION_ID
        ),
        new_reservation_party_size=4,
        capacity_request=request,
        reservations=[],
        tables=tables,
        combinations=[],
        learning_snapshot=_snapshot(),
        calibration=_calibration(),
    )

    assert len(runner.calls) == 1

    call = runner.calls[0]

    assert call["request"] is request
    assert call["plan"] is plan
    assert call["reservations"] == []
    assert call["tables"] is tables
    assert call["combinations"] == []

    assert (
        call["new_reservation_id"]
        == str(NEW_RESERVATION_ID)
    )

    assert (
        call["new_reservation_party_size"]
        == 4
    )


def test_safe_resolution_produces_context():
    result = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=(
                RecordingCapacityRunner()
            )
        )
        .resolve(
            plan=_plan(),
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=_snapshot(),
            calibration=_calibration(),
        )
    )

    assert result.context is not None

    assert (
        result.context.calibration_state
        == TemporalCalibrationState.WELL_CALIBRATED
    )

    assert (
        result.context
        .lost_future_available_slots
        == 0
    )

    assert (
        result.context
        .marginal_capacity_loss_ratio
        == 0.0
    )


def test_capacity_loss_is_preserved():
    runner = RecordingCapacityRunner(
        baseline=_profile(
            [True, True, True]
        ),
        candidate=_profile(
            [True, False, True]
        ),
    )

    result = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=runner,
        )
        .resolve(
            plan=_plan(),
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=_snapshot(),
            calibration=_calibration(),
        )
    )

    assert (
        result.capacity_evidence
        .lost_future_available_slots
        == 1
    )

    assert (
        result.capacity_evidence
        .marginal_capacity_loss_ratio
        > 0.0
    )


def test_non_well_calibration_is_preserved():
    result = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=(
                RecordingCapacityRunner()
            )
        )
        .resolve(
            plan=_plan(),
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .UNDERPREDICTING
            ),
        )
    )

    assert result.context is not None

    assert (
        result.context.calibration_state
        == TemporalCalibrationState
        .UNDERPREDICTING
    )


def test_missing_calibration_fails_closed():
    result = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=(
                RecordingCapacityRunner()
            )
        )
        .resolve(
            plan=_plan(),
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=_snapshot(),
            calibration=None,
        )
    )

    assert result.context is None

    assert (
        result.orchestration
        .safety_result
        .complete
        is False
    )


def test_low_turn_evidence_fails_closed():
    empty_snapshot = (
        TemporalLearningSnapshot(
            restaurant_id=RESTAURANT_ID,
            generated_from_sample_count=0,
        )
    )

    result = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=(
                RecordingCapacityRunner()
            )
        )
        .resolve(
            plan=_plan(),
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=(
                empty_snapshot
            ),
            calibration=_calibration(),
        )
    )

    assert result.context is None

    assert (
        result.orchestration
        .safety_result
        .complete
        is False
    )


def test_resolution_exposes_evidence_not_authority():
    result = (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=(
                RecordingCapacityRunner()
            )
        )
        .resolve(
            plan=_plan(),
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=_snapshot(),
            calibration=_calibration(),
        )
    )

    assert not hasattr(result, "allowed")

    assert not hasattr(
        result,
        "execution_eligibility",
    )

    assert not hasattr(
        result,
        "autopilot_enabled",
    )


def test_resolver_does_not_mutate_plan():
    plan = _plan()

    original_score = plan.score
    original_assignment = (
        plan.new_reservation_assignment
    )

    (
        TemporalReoptimizationSafetyResolver(
            capacity_runner=(
                RecordingCapacityRunner()
            )
        )
        .resolve(
            plan=plan,
            new_reservation_id=(
                NEW_RESERVATION_ID
            ),
            new_reservation_party_size=4,
            capacity_request=_request(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            learning_snapshot=_snapshot(),
            calibration=_calibration(),
        )
    )

    assert plan.score == original_score

    assert (
        plan.new_reservation_assignment
        is original_assignment
    )