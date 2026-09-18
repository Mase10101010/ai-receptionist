from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    ExistingReservation,
    ReoptimizationPlan,
    ReservationMove,
    ScoredAssignment,
)
from app.intelligence_temporal.reoptimization_scenario import (
    TemporalReoptimizationScenarioBuilder,
)


NOW = datetime(
    2026,
    9,
    8,
    19,
    0,
    tzinfo=timezone.utc,
)


def _reservation(
    *,
    reservation_id: str,
    table_ids: tuple[str, ...],
):
    return ExistingReservation(
        id=reservation_id,
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=4,
        table_ids=table_ids,
    )


def _assignment(
    *,
    table_ids: tuple[str, ...],
):
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=table_ids[0],
            table_ids=table_ids,
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
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
    *,
    reservation_id: str,
    from_table_ids: tuple[str, ...],
    to_table_ids: tuple[str, ...],
):
    return ReservationMove(
        reservation_id=reservation_id,
        from_table_ids=from_table_ids,
        to_table_ids=to_table_ids,
        party_size=4,
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        destination_capacity=4,
        seat_waste=0,
        explanation="Move.",
    )


def _plan(
    *,
    new_table_ids=("table-1",),
    moves=(),
):
    return ReoptimizationPlan(
        new_reservation_assignment=_assignment(
            table_ids=new_table_ids,
        ),
        moves=tuple(moves),
        score=90.0,
        total_seat_waste=0,
        moved_reservations_count=len(moves),
        explanation="Plan.",
    )


def test_adds_new_reservation_to_candidate_state():
    result = (
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[],
            plan=_plan(),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    assert result.baseline_reservations == ()

    assert len(result.candidate_reservations) == 1

    created = result.candidate_reservations[0]

    assert created.id == "new"
    assert created.table_ids == ("table-1",)
    assert created.party_size == 4


def test_moves_existing_reservation_to_destination_tables():
    existing = _reservation(
        reservation_id="existing",
        table_ids=("table-1",),
    )

    result = (
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[existing],
            plan=_plan(
                new_table_ids=("table-1",),
                moves=[
                    _move(
                        reservation_id="existing",
                        from_table_ids=("table-1",),
                        to_table_ids=("table-2",),
                    ),
                ],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    candidate = {
        item.id: item
        for item in result.candidate_reservations
    }

    assert (
        candidate["existing"].table_ids
        == ("table-2",)
    )

    assert (
        candidate["new"].table_ids
        == ("table-1",)
    )


def test_move_preserves_existing_reservation_time():
    existing = _reservation(
        reservation_id="existing",
        table_ids=("table-1",),
    )

    result = (
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[existing],
            plan=_plan(
                moves=[
                    _move(
                        reservation_id="existing",
                        from_table_ids=("table-1",),
                        to_table_ids=("table-2",),
                    ),
                ],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    candidate = {
        item.id: item
        for item in result.candidate_reservations
    }

    moved = candidate["existing"]

    assert moved.start_at == existing.start_at
    assert moved.end_at == existing.end_at


def test_baseline_is_not_mutated():
    existing = _reservation(
        reservation_id="existing",
        table_ids=("table-1",),
    )

    result = (
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[existing],
            plan=_plan(
                moves=[
                    _move(
                        reservation_id="existing",
                        from_table_ids=("table-1",),
                        to_table_ids=("table-2",),
                    ),
                ],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    assert existing.table_ids == ("table-1",)

    assert (
        result.baseline_reservations[0]
        .table_ids
        == ("table-1",)
    )


def test_missing_moved_reservation_fails():
    with pytest.raises(
        ValueError,
        match="missing",
    ):
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[],
            plan=_plan(
                moves=[
                    _move(
                        reservation_id="missing",
                        from_table_ids=("table-1",),
                        to_table_ids=("table-2",),
                    ),
                ],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )


def test_duplicate_move_fails():
    move = _move(
        reservation_id="existing",
        from_table_ids=("table-1",),
        to_table_ids=("table-2",),
    )

    with pytest.raises(
        ValueError,
        match="more than once",
    ):
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[
                _reservation(
                    reservation_id="existing",
                    table_ids=("table-1",),
                ),
            ],
            plan=_plan(
                moves=[move, move],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )


def test_new_reservation_must_not_exist_in_baseline():
    with pytest.raises(
        ValueError,
        match="new reservation",
    ):
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[
                _reservation(
                    reservation_id="new",
                    table_ids=("table-9",),
                ),
            ],
            plan=_plan(),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )


def test_multiple_moves_are_applied():
    reservations = [
        _reservation(
            reservation_id="r1",
            table_ids=("table-1",),
        ),
        _reservation(
            reservation_id="r2",
            table_ids=("table-2",),
        ),
    ]

    result = (
        TemporalReoptimizationScenarioBuilder.build(
            reservations=reservations,
            plan=_plan(
                new_table_ids=("table-1",),
                moves=[
                    _move(
                        reservation_id="r1",
                        from_table_ids=("table-1",),
                        to_table_ids=("table-3",),
                    ),
                    _move(
                        reservation_id="r2",
                        from_table_ids=("table-2",),
                        to_table_ids=("table-4",),
                    ),
                ],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    candidate = {
        item.id: item
        for item in result.candidate_reservations
    }

    assert candidate["r1"].table_ids == (
        "table-3",
    )
    assert candidate["r2"].table_ids == (
        "table-4",
    )
    assert candidate["new"].table_ids == (
        "table-1",
    )


def test_reports_exact_moved_reservation_ids():
    result = (
        TemporalReoptimizationScenarioBuilder.build(
            reservations=[
                _reservation(
                    reservation_id="r1",
                    table_ids=("table-1",),
                ),
            ],
            plan=_plan(
                moves=[
                    _move(
                        reservation_id="r1",
                        from_table_ids=("table-1",),
                        to_table_ids=("table-2",),
                    ),
                ],
            ),
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    assert result.moved_reservation_ids == (
        "r1",
    )