from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import pytest

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
TABLE_ID = uuid4()


def _table() -> IntelligenceTable:
    return IntelligenceTable(
        id=str(TABLE_ID),
        table_number="1",
        min_capacity=1,
        max_capacity=4,
        area_id="main",
    )


def _candidate(
    *,
    duration_minutes: int = 60,
) -> ScoredAssignment:
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(TABLE_ID),
            table_ids=(str(TABLE_ID),),
            start_at=NOW,
            end_at=(
                NOW
                + timedelta(
                    minutes=duration_minutes,
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


def _request() -> FutureCapacityRequest:
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=4,
        duration_minutes=30,
        horizon_minutes=90,
        slot_minutes=30,
    )


def test_default_propagation_uses_technical_duration():
    candidate = _candidate(
        duration_minutes=60,
    )

    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[_table()],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.occupancy_duration_minutes == 60


def test_explicit_occupancy_changes_counterfactual_capacity_only():
    candidate = _candidate(
        duration_minutes=60,
    )

    technical = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[_table()],
        combinations=[],
        candidate_party_size=2,
    )

    temporal = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[_table()],
        combinations=[],
        candidate_party_size=2,
        candidate_occupancy_duration_minutes=90,
    )

    assert (
        temporal.occupancy_duration_minutes
        == 90
    )

    assert (
        temporal.counterfactual
        .candidate_available_slots
        <
        technical.counterfactual
        .candidate_available_slots
    )


def test_explicit_occupancy_does_not_modify_technical_candidate_end():
    candidate = _candidate(
        duration_minutes=60,
    )

    original_end_at = candidate.candidate.end_at

    result = TemporalCandidateEvaluator().evaluate(
        request=_request(),
        candidate=candidate,
        reservations=[],
        tables=[_table()],
        combinations=[],
        candidate_party_size=2,
        candidate_occupancy_duration_minutes=90,
    )

    assert result.candidate.end_at == original_end_at
    assert candidate.candidate.end_at == original_end_at

    assert result.occupancy_duration_minutes == 90


def test_invalid_explicit_occupancy_fails_closed():
    with pytest.raises(
        ValueError,
        match="occupancy duration",
    ):
        TemporalCandidateEvaluator().evaluate(
            request=_request(),
            candidate=_candidate(),
            reservations=[],
            tables=[_table()],
            combinations=[],
            candidate_party_size=2,
            candidate_occupancy_duration_minutes=0,
        )
