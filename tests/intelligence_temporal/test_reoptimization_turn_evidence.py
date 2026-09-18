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
    ReoptimizationPlan,
    ReservationMove,
    ScoredAssignment,
)
from app.intelligence_temporal.learning import (
    PartySizeTurnProfile,
    TemporalSampleState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)
from app.intelligence_temporal.reoptimization_turn_evidence import (
    TemporalReoptimizationTurnEvidenceService,
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

TABLE_1 = str(uuid4())
TABLE_2 = str(uuid4())


def _table(
    table_id: str,
):
    return IntelligenceTable(
        id=table_id,
        table_number=table_id,
        min_capacity=1,
        max_capacity=4,
    )


def _assignment():
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=TABLE_1,
            table_ids=(TABLE_1,),
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


def _move(
    reservation_id,
    *,
    party_size=4,
):
    return ReservationMove(
        reservation_id=str(
            reservation_id
        ),
        from_table_ids=(TABLE_1,),
        to_table_ids=(TABLE_2,),
        party_size=party_size,
        start_at=NOW,
        end_at=(
            NOW
            + timedelta(minutes=90)
        ),
        destination_capacity=4,
        seat_waste=0,
        explanation="Move.",
    )


def _plan(
    *,
    moves=(),
):
    return ReoptimizationPlan(
        new_reservation_assignment=(
            _assignment()
        ),
        moves=tuple(moves),
        score=90.0,
        total_seat_waste=0,
        moved_reservations_count=(
            len(moves)
        ),
        explanation="Plan.",
    )


def _profile(
    *,
    party_size=4,
    sample_count=40,
):
    return PartySizeTurnProfile(
        restaurant_id=RESTAURANT_ID,
        party_size=party_size,
        sample_count=sample_count,
        included_sample_count=sample_count,
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


def _snapshot(
    *,
    profiles=None,
):
    profiles = (
        profiles
        if profiles is not None
        else [_profile()]
    )

    return TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=sum(
            profile.sample_count
            for profile in profiles
        ),
        party_size_profiles=profiles,
    )


def test_new_reservation_high_confidence():
    new_id = uuid4()

    result = (
        TemporalReoptimizationTurnEvidenceService
        .evaluate(
            plan=_plan(),
            new_reservation_id=new_id,
            new_reservation_party_size=4,
            snapshot=_snapshot(),
            tables=[
                _table(TABLE_1),
                _table(TABLE_2),
            ],
        )
    )

    assert len(
        result.affected_reservations
    ) == 1

    assert (
        result.affected_reservations[0]
        .reservation_id
        == new_id
    )

    assert (
        result.affected_reservations[0]
        .expected_turn_confidence
        == ExpectedTurnConfidence.HIGH
    )


def test_moved_reservation_is_included():
    moved_id = uuid4()

    result = (
        TemporalReoptimizationTurnEvidenceService
        .evaluate(
            plan=_plan(
                moves=[
                    _move(moved_id),
                ],
            ),
            new_reservation_id=uuid4(),
            new_reservation_party_size=4,
            snapshot=_snapshot(),
            tables=[
                _table(TABLE_1),
                _table(TABLE_2),
            ],
        )
    )

    ids = {
        item.reservation_id
        for item
        in result.affected_reservations
    }

    assert moved_id in ids
    assert len(ids) == 2


def test_multiple_moves_are_all_included():
    first = uuid4()
    second = uuid4()

    result = (
        TemporalReoptimizationTurnEvidenceService
        .evaluate(
            plan=_plan(
                moves=[
                    _move(first),
                    _move(second),
                ],
            ),
            new_reservation_id=uuid4(),
            new_reservation_party_size=4,
            snapshot=_snapshot(),
            tables=[
                _table(TABLE_1),
                _table(TABLE_2),
            ],
        )
    )

    assert len(
        result.affected_reservations
    ) == 3


def test_missing_learned_pattern_returns_low():
    result = (
        TemporalReoptimizationTurnEvidenceService
        .evaluate(
            plan=_plan(),
            new_reservation_id=uuid4(),
            new_reservation_party_size=4,
            snapshot=_snapshot(
                profiles=[],
            ),
            tables=[
                _table(TABLE_1),
            ],
        )
    )

    assert (
        result.affected_reservations[0]
        .expected_turn_confidence
        == ExpectedTurnConfidence.LOW
    )


def test_medium_sample_count_returns_medium():
    result = (
        TemporalReoptimizationTurnEvidenceService
        .evaluate(
            plan=_plan(),
            new_reservation_id=uuid4(),
            new_reservation_party_size=4,
            snapshot=_snapshot(
                profiles=[
                    _profile(
                        sample_count=20,
                    ),
                ],
            ),
            tables=[
                _table(TABLE_1),
            ],
        )
    )

    assert (
        result.affected_reservations[0]
        .expected_turn_confidence
        == ExpectedTurnConfidence.MEDIUM
    )


def test_each_reservation_uses_its_party_size():
    moved_id = uuid4()

    result = (
        TemporalReoptimizationTurnEvidenceService
        .evaluate(
            plan=_plan(
                moves=[
                    _move(
                        moved_id,
                        party_size=6,
                    ),
                ],
            ),
            new_reservation_id=uuid4(),
            new_reservation_party_size=4,
            snapshot=_snapshot(
                profiles=[
                    _profile(
                        party_size=4,
                        sample_count=40,
                    ),
                    _profile(
                        party_size=6,
                        sample_count=20,
                    ),
                ],
            ),
            tables=[
                _table(TABLE_1),
                _table(TABLE_2),
            ],
        )
    )

    by_id = {
        item.reservation_id: item
        for item
        in result.affected_reservations
    }

    assert (
        by_id[moved_id]
        .expected_turn_confidence
        == ExpectedTurnConfidence.MEDIUM
    )


def test_invalid_moved_reservation_id_fails():
    move = ReservationMove(
        reservation_id="not-a-uuid",
        from_table_ids=(TABLE_1,),
        to_table_ids=(TABLE_2,),
        party_size=4,
        start_at=NOW,
        end_at=(
            NOW + timedelta(minutes=90)
        ),
        destination_capacity=4,
        seat_waste=0,
        explanation="Move.",
    )

    with pytest.raises(
        ValueError,
        match="valid UUID",
    ):
        (
            TemporalReoptimizationTurnEvidenceService
            .evaluate(
                plan=_plan(
                    moves=[move],
                ),
                new_reservation_id=uuid4(),
                new_reservation_party_size=4,
                snapshot=_snapshot(),
                tables=[
                    _table(TABLE_1),
                    _table(TABLE_2),
                ],
            )
        )


def test_duplicate_affected_reservation_fails():
    reservation_id = uuid4()

    with pytest.raises(
        ValueError,
        match="unique",
    ):
        (
            TemporalReoptimizationTurnEvidenceService
            .evaluate(
                plan=_plan(
                    moves=[
                        _move(
                            reservation_id
                        ),
                    ],
                ),
                new_reservation_id=(
                    reservation_id
                ),
                new_reservation_party_size=4,
                snapshot=_snapshot(),
                tables=[
                    _table(TABLE_1),
                    _table(TABLE_2),
                ],
            )
        )


def test_invalid_duration_fails_closed():
    assignment = _assignment()

    invalid_candidate = (
        assignment.candidate
    )

    invalid_candidate = (
        CandidateAssignment(
            kind=invalid_candidate.kind,
            resource_id=(
                invalid_candidate.resource_id
            ),
            table_ids=(
                invalid_candidate.table_ids
            ),
            start_at=NOW,
            end_at=NOW,
            capacity=invalid_candidate.capacity,
            minimum_capacity=(
                invalid_candidate.minimum_capacity
            ),
            area_id=None,
            floor_id=None,
        )
    )

    invalid_assignment = ScoredAssignment(
        candidate=invalid_candidate,
        score=assignment.score,
        seat_waste=assignment.seat_waste,
        fragmentation_minutes=(
            assignment.fragmentation_minutes
        ),
        explanation=assignment.explanation,
    )

    plan = ReoptimizationPlan(
        new_reservation_assignment=(
            invalid_assignment
        ),
        moves=(),
        score=90.0,
        total_seat_waste=0,
        moved_reservations_count=0,
        explanation="Plan.",
    )

    with pytest.raises(
        ValueError,
        match="duration",
    ):
        (
            TemporalReoptimizationTurnEvidenceService
            .evaluate(
                plan=plan,
                new_reservation_id=uuid4(),
                new_reservation_party_size=4,
                snapshot=_snapshot(),
                tables=[
                    _table(TABLE_1),
                ],
            )
        )