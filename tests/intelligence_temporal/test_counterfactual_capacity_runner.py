from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    IntelligenceTable,
    ScoredAssignment,
)
from app.intelligence_temporal.counterfactual_capacity_runner import (
    TemporalCounterfactualCapacityRunner,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)

RESTAURANT_ID = uuid4()

TABLE_1 = uuid4()
TABLE_2 = uuid4()


def _tables() -> list[IntelligenceTable]:
    return [
        IntelligenceTable(
            id=str(TABLE_1),
            table_number="1",
            min_capacity=1,
            max_capacity=4,
            area_id="main",
        ),
        IntelligenceTable(
            id=str(TABLE_2),
            table_number="2",
            min_capacity=1,
            max_capacity=4,
            area_id="main",
        ),
    ]


def _candidate(
    *,
    table_id=TABLE_1,
    start_at=NOW,
    duration_minutes: int = 90,
) -> ScoredAssignment:
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(table_id),
            table_ids=(str(table_id),),
            start_at=start_at,
            end_at=(
                start_at
                + timedelta(
                    minutes=duration_minutes
                )
            ),
            capacity=4,
            minimum_capacity=1,
            area_id="main",
            floor_id=None,
            setup_minutes=0,
        ),
        score=100.0,
        seat_waste=2,
        fragmentation_minutes=0,
        explanation="Candidate.",
    )


def _request(
    *,
    party_size: int = 4,
    duration_minutes: int = 90,
    horizon_minutes: int = 120,
    slot_minutes: int = 30,
) -> FutureCapacityRequest:
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=party_size,
        duration_minutes=duration_minutes,
        horizon_minutes=horizon_minutes,
        slot_minutes=slot_minutes,
    )


def test_baseline_and_candidate_use_same_slots():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(),
            candidate=_candidate(),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert [
        slot.start_at
        for slot in result.baseline.slots
    ] == [
        slot.start_at
        for slot in result.candidate.slots
    ]


def test_baseline_preserves_direct_capacity():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(),
            candidate=_candidate(),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert all(
        slot.directly_available
        for slot in result.baseline.slots
    )


def test_candidate_scenario_can_remove_future_capacity():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(
                party_size=4,
                horizon_minutes=60,
            ),
            candidate=_candidate(
                table_id=TABLE_1,
                start_at=NOW,
                duration_minutes=90,
            ),
            reservations=[],
            tables=[
                IntelligenceTable(
                    id=str(TABLE_1),
                    table_number="1",
                    min_capacity=1,
                    max_capacity=4,
                    area_id="main",
                ),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert [
        slot.directly_available
        for slot in result.baseline.slots
    ] == [
        True,
        True,
        True,
    ]

    assert [
        slot.directly_available
        for slot in result.candidate.slots
    ] == [
        False,
        False,
        False,
    ]


def test_other_table_can_preserve_capacity():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(
                party_size=4,
                horizon_minutes=60,
            ),
            candidate=_candidate(
                table_id=TABLE_1,
            ),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert all(
        slot.directly_available
        for slot in result.candidate.slots
    )


def test_candidate_capacity_recovers_after_candidate_end():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(
                party_size=4,
                duration_minutes=30,
                horizon_minutes=120,
                slot_minutes=30,
            ),
            candidate=_candidate(
                table_id=TABLE_1,
                duration_minutes=60,
            ),
            reservations=[],
            tables=[
                IntelligenceTable(
                    id=str(TABLE_1),
                    table_number="1",
                    min_capacity=1,
                    max_capacity=4,
                    area_id="main",
                ),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    availability = [
        slot.directly_available
        for slot in result.candidate.slots
    ]

    assert availability[0] is False
    assert availability[1] is False

    assert availability[2:] == [
        True,
        True,
        True,
    ]


def test_profile_metadata_is_preserved():
    request = _request()

    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=request,
            candidate=_candidate(),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert (
        result.baseline.restaurant_id
        == request.restaurant_id
    )
    assert (
        result.candidate.restaurant_id
        == request.restaurant_id
    )

    assert result.baseline.start_at == request.start_at
    assert result.candidate.start_at == request.start_at

    assert (
        result.baseline.horizon_minutes
        == request.horizon_minutes
    )


def test_available_slot_preserves_real_table_identity():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(
                horizon_minutes=0,
            ),
            candidate=_candidate(
                table_id=TABLE_1,
                start_at=(
                    NOW
                    + timedelta(hours=3)
                ),
            ),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    slot = result.baseline.slots[0]

    assert slot.directly_available is True
    assert len(slot.table_ids) == 1

    assert slot.table_ids[0] in {
        TABLE_1,
        TABLE_2,
    }

    assert slot.assignment_capacity == 4


def test_summary_reflects_candidate_capacity_loss():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(
                party_size=4,
                horizon_minutes=60,
            ),
            candidate=_candidate(),
            reservations=[],
            tables=[
                IntelligenceTable(
                    id=str(TABLE_1),
                    table_number="1",
                    min_capacity=1,
                    max_capacity=4,
                    area_id="main",
                ),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert (
        result.baseline.summary
        .directly_available_slots
        == 3
    )

    assert (
        result.candidate.summary
        .directly_available_slots
        == 0
    )


def test_does_not_modify_optimizer_ranking_contract():
    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(
                horizon_minutes=0,
            ),
            candidate=_candidate(
                start_at=(
                    NOW
                    + timedelta(hours=3)
                ),
            ),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    slot = result.baseline.slots[0]

    # Existing optimizer chooses one valid assignment.
    # T7.4 only consumes that truth.
    assert slot.directly_available is True
    assert slot.seat_waste == 0


def test_runner_preserves_default_technical_occupancy():
    candidate = _candidate(
        duration_minutes=90,
    )

    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(),
            candidate=candidate,
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
        )
    )

    technical_duration_minutes = int(
        (
            candidate.candidate.end_at
            - candidate.candidate.start_at
        ).total_seconds()
        // 60
    )

    assert (
        result.candidate_occupancy_duration_minutes
        == technical_duration_minutes
    )


def test_runner_propagates_explicit_temporal_occupancy():
    candidate = _candidate(
        duration_minutes=90,
    )

    original_end_at = candidate.candidate.end_at

    result = (
        TemporalCounterfactualCapacityRunner()
        .run(
            request=_request(),
            candidate=candidate,
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=2,
            candidate_occupancy_duration_minutes=105,
        )
    )

    assert (
        result.candidate_occupancy_duration_minutes
        == 105
    )

    assert candidate.candidate.end_at == original_end_at

