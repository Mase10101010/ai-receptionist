from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    ExistingReservation,
    IntelligenceTable,
    OptimizationResult,
    ReoptimizationPlan,
    ReservationMove,
    ScoredAssignment,
)
from app.intelligence_temporal.reoptimization_capacity_runner import (
    TemporalReoptimizationCapacityRunner,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
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
    number: str,
):
    return IntelligenceTable(
        id=table_id,
        table_number=number,
        min_capacity=1,
        max_capacity=4,
    )


def _scored_assignment(
    *,
    table_id: str,
    start_at=NOW,
):
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=table_id,
            table_ids=(table_id,),
            start_at=start_at,
            end_at=(
                start_at
                + timedelta(minutes=30)
            ),
            capacity=4,
            minimum_capacity=1,
            area_id=None,
            floor_id=None,
        ),
        score=90.0,
        seat_waste=0,
        fragmentation_minutes=0,
        explanation="Available.",
    )


def _plan(
    *,
    new_table_id=TABLE_1,
    moves=(),
):
    return ReoptimizationPlan(
        new_reservation_assignment=(
            _scored_assignment(
                table_id=new_table_id,
            )
        ),
        moves=tuple(moves),
        score=90.0,
        total_seat_waste=0,
        moved_reservations_count=len(moves),
        explanation="Plan.",
    )


def _reservation(
    *,
    reservation_id: str,
    table_id: str,
):
    return ExistingReservation(
        id=reservation_id,
        start_at=NOW,
        end_at=NOW + timedelta(minutes=30),
        party_size=4,
        table_ids=(table_id,),
    )


def _move(
    *,
    reservation_id: str,
    from_table_id: str,
    to_table_id: str,
):
    return ReservationMove(
        reservation_id=reservation_id,
        from_table_ids=(from_table_id,),
        to_table_ids=(to_table_id,),
        party_size=4,
        start_at=NOW,
        end_at=NOW + timedelta(minutes=30),
        destination_capacity=4,
        seat_waste=0,
        explanation="Move.",
    )


def _request():
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=4,
        duration_minutes=30,
        horizon_minutes=60,
        slot_minutes=30,
    )


class RecordingOptimizer:
    def __init__(self):
        self.calls = []

    def optimize(
        self,
        *,
        request,
        tables,
        reservations,
        combinations,
    ):
        self.calls.append(
            {
                "request": request,
                "reservations": tuple(
                    reservations
                ),
            }
        )

        occupied = {
            table_id
            for reservation in reservations
            if (
                reservation.start_at
                < (
                    request.requested_start
                    + timedelta(
                        minutes=(
                            request.duration_minutes
                        )
                    )
                )
                and reservation.end_at
                > request.requested_start
            )
            for table_id in reservation.table_ids
        }

        available = next(
            (
                table.id
                for table in tables
                if table.id not in occupied
            ),
            None,
        )

        if available is None:
            return OptimizationResult(
                available=False,
                recommended=None,
            )

        return OptimizationResult(
            available=True,
            recommended=_scored_assignment(
                table_id=available,
                start_at=request.requested_start,
            ),
        )


def test_runs_baseline_and_candidate_for_every_slot():
    optimizer = RecordingOptimizer()

    runner = (
        TemporalReoptimizationCapacityRunner(
            optimizer=optimizer,
        )
    )

    result = runner.run(
        request=_request(),
        plan=_plan(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        new_reservation_id="new",
        new_reservation_party_size=4,
    )

    # 0, 30, 60 minutes = 3 slots.
    # baseline + candidate = 6 optimizer calls.
    assert len(optimizer.calls) == 6

    assert len(result.baseline.slots) == 3
    assert len(result.candidate.slots) == 3


def test_same_future_capacity_request_is_used():
    optimizer = RecordingOptimizer()

    TemporalReoptimizationCapacityRunner(
        optimizer=optimizer,
    ).run(
        request=_request(),
        plan=_plan(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        new_reservation_id="new",
        new_reservation_party_size=4,
    )

    requested_starts = [
        call["request"].requested_start
        for call in optimizer.calls
    ]

    assert requested_starts[:3] == [
        NOW,
        NOW + timedelta(minutes=30),
        NOW + timedelta(minutes=60),
    ]

    assert requested_starts[3:] == [
        NOW,
        NOW + timedelta(minutes=30),
        NOW + timedelta(minutes=60),
    ]


def test_candidate_profile_contains_new_reservation():
    optimizer = RecordingOptimizer()

    TemporalReoptimizationCapacityRunner(
        optimizer=optimizer,
    ).run(
        request=_request(),
        plan=_plan(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        new_reservation_id="new",
        new_reservation_party_size=4,
    )

    baseline_calls = optimizer.calls[:3]
    candidate_calls = optimizer.calls[3:]

    assert all(
        not call["reservations"]
        for call in baseline_calls
    )

    assert all(
        any(
            reservation.id == "new"
            for reservation
            in call["reservations"]
        )
        for call in candidate_calls
    )


def test_moved_reservation_is_reflected_in_candidate_profile():
    optimizer = RecordingOptimizer()

    existing = _reservation(
        reservation_id="existing",
        table_id=TABLE_1,
    )

    result = (
        TemporalReoptimizationCapacityRunner(
            optimizer=optimizer,
        )
        .run(
            request=_request(),
            plan=_plan(
                new_table_id=TABLE_1,
                moves=[
                    _move(
                        reservation_id="existing",
                        from_table_id=TABLE_1,
                        to_table_id=TABLE_2,
                    ),
                ],
            ),
            reservations=[existing],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    candidate_reservations = (
        optimizer.calls[3]["reservations"]
    )

    by_id = {
        reservation.id: reservation
        for reservation
        in candidate_reservations
    }

    assert (
        by_id["existing"].table_ids
        == (TABLE_2,)
    )

    assert (
        by_id["new"].table_ids
        == (TABLE_1,)
    )

    assert result.moved_reservation_ids == (
        "existing",
    )


def test_plan_can_reduce_future_direct_availability():
    optimizer = RecordingOptimizer()

    result = (
        TemporalReoptimizationCapacityRunner(
            optimizer=optimizer,
        )
        .run(
            request=_request(),
            plan=_plan(
                new_table_id=TABLE_1,
            ),
            reservations=[
                _reservation(
                    reservation_id="existing",
                    table_id=TABLE_2,
                ),
            ],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            new_reservation_id="new",
            new_reservation_party_size=4,
        )
    )

    assert (
        result.baseline.slots[0]
        .directly_available
        is True
    )

    assert (
        result.candidate.slots[0]
        .directly_available
        is False
    )


def test_baseline_reservations_are_not_mutated():
    optimizer = RecordingOptimizer()

    existing = _reservation(
        reservation_id="existing",
        table_id=TABLE_1,
    )

    TemporalReoptimizationCapacityRunner(
        optimizer=optimizer,
    ).run(
        request=_request(),
        plan=_plan(
            moves=[
                _move(
                    reservation_id="existing",
                    from_table_id=TABLE_1,
                    to_table_id=TABLE_2,
                ),
            ],
        ),
        reservations=[existing],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        new_reservation_id="new",
        new_reservation_party_size=4,
    )

    assert existing.table_ids == (
        TABLE_1,
    )


def test_run_preserves_plan_identity():
    optimizer = RecordingOptimizer()

    result = (
        TemporalReoptimizationCapacityRunner(
            optimizer=optimizer,
        )
        .run(
            request=_request(),
            plan=_plan(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            new_reservation_id="reservation-new",
            new_reservation_party_size=4,
        )
    )

    assert (
        result.new_reservation_id
        == "reservation-new"
    )

    assert result.moved_reservation_ids == ()