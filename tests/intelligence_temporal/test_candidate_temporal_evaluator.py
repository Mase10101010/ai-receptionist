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
from app.intelligence_temporal.candidate_temporal_evaluator import (
    TemporalCandidateEvaluator,
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


def _table(
    table_id,
    number: str,
) -> IntelligenceTable:
    return IntelligenceTable(
        id=str(table_id),
        table_number=number,
        min_capacity=1,
        max_capacity=4,
        area_id="main",
    )


def _candidate(
    *,
    table_id=TABLE_1,
    duration_minutes: int = 90,
) -> ScoredAssignment:
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(table_id),
            table_ids=(str(table_id),),
            start_at=NOW,
            end_at=(
                NOW
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
        score=90.0,
        seat_waste=0,
        fragmentation_minutes=0,
        explanation="Candidate.",
    )


def _request(
    *,
    horizon_minutes: int = 60,
    duration_minutes: int = 30,
) -> FutureCapacityRequest:
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=4,
        duration_minutes=duration_minutes,
        horizon_minutes=horizon_minutes,
        slot_minutes=30,
    )


def test_returns_candidate_identity():
    candidate = _candidate()

    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.candidate.table_ids == [
        TABLE_1,
    ]

    assert result.candidate.score == 90.0


def test_single_table_candidate_can_create_temporal_cost():
    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=_candidate(
            duration_minutes=90,
        ),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert (
        result.counterfactual.cost
        .lost_future_available_slots
        > 0
    )

    assert (
        result.counterfactual.cost
        .has_temporal_cost
        is True
    )


def test_spare_table_can_preserve_future_capacity():
    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=_candidate(
            duration_minutes=90,
        ),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert (
        result.counterfactual.cost
        .lost_future_available_slots
        == 0
    )

    assert (
        result.counterfactual.cost
        .has_temporal_cost
        is False
    )


def test_preserves_existing_technical_signals():
    candidate = _candidate()

    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    cost = result.counterfactual.cost

    assert cost.base_score == candidate.score
    assert cost.seat_waste == candidate.seat_waste
    assert (
        cost.fragmentation_minutes
        == candidate.fragmentation_minutes
    )


def test_evaluated_slot_count_matches_profile():
    result = TemporalCandidateEvaluator().evaluate(
        request=_request(
            horizon_minutes=60,
        ),
        candidate=_candidate(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert (
        result.counterfactual.evaluated_slots
        == 3
    )


def test_future_capacity_recovers_after_candidate_end():
    result = TemporalCandidateEvaluator().evaluate(
        request=_request(
            horizon_minutes=120,
            duration_minutes=30,
        ),
        candidate=_candidate(
            duration_minutes=60,
        ),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    cost = result.counterfactual.cost

    assert (
        cost.first_future_capacity_loss_at
        is not None
    )

    assert (
        cost.last_future_capacity_loss_at
        is not None
    )


def test_candidate_table_number_is_resolved():
    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=_candidate(),
        reservations=[],
        tables=[
            _table(TABLE_1, "12"),
            _table(TABLE_2, "13"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.candidate.table_numbers == [
        "12",
    ]


def test_evaluator_exposes_effective_occupancy_duration():
    candidate = _candidate(
        duration_minutes=90,
    )

    original_end_at = candidate.candidate.end_at

    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
        candidate_occupancy_duration_minutes=105,
    )

    assert result.occupancy_duration_minutes == 105

    technical_duration_minutes = int(
        (
            result.candidate.end_at
            - result.candidate.start_at
        ).total_seconds()
        // 60
    )

    assert technical_duration_minutes == 90
    assert candidate.candidate.end_at == original_end_at

