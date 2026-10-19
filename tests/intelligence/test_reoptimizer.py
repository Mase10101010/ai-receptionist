from datetime import datetime, timedelta, timezone

from app.intelligence.reoptimizer import (
    ReservationReoptimizer,
)
from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    ReoptimizationRequest,
    TableCombination,
)


NOW = datetime(
    2026,
    8,
    17,
    19,
    0,
    tzinfo=timezone.utc,
)


def build_tables() -> list[IntelligenceTable]:
    return [
        IntelligenceTable(
            id="table-1",
            table_number="1",
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        ),
        IntelligenceTable(
            id="table-2",
            table_number="2",
            min_capacity=1,
            max_capacity=4,
            area_id="main",
        ),
        IntelligenceTable(
            id="table-3",
            table_number="3",
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        ),
    ]


def build_combinations() -> list[TableCombination]:
    return [
        TableCombination(
            id="combination-1-2",
            name="Tables 1 + 2",
            table_ids=("table-1", "table-2"),
            min_capacity=5,
            max_capacity=6,
            setup_minutes=5,
        ),
    ]


def test_returns_direct_assignment_without_moves():
    engine = ReservationReoptimizer()

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=6,
            duration_minutes=120,
        ),
        tables=build_tables(),
        reservations=[],
        combinations=build_combinations(),
    )

    assert result.available is True
    assert result.recommended is not None
    assert result.recommended.moves == ()
    assert (
        result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
        == ("table-1", "table-2")
    )


def test_moves_one_reservation_to_free_combination():
    engine = ReservationReoptimizer()

    existing = ExistingReservation(
        id="reservation-small",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=120),
        party_size=2,
        table_ids=("table-1",),
        locked=False,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=6,
            duration_minutes=120,
        ),
        tables=build_tables(),
        reservations=[existing],
        combinations=build_combinations(),
    )

    assert result.available is True
    assert result.recommended is not None
    assert result.recommended.moved_reservations_count == 1

    move = result.recommended.moves[0]

    assert move.reservation_id == "reservation-small"
    assert move.from_table_ids == ("table-1",)
    assert move.to_table_ids == ("table-3",)

    assert (
        result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
        == ("table-1", "table-2")
    )


def test_does_not_move_locked_reservation():
    engine = ReservationReoptimizer()

    existing = ExistingReservation(
        id="reservation-locked",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=120),
        party_size=2,
        table_ids=("table-1",),
        locked=True,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=6,
            duration_minutes=120,
        ),
        tables=build_tables(),
        reservations=[existing],
        combinations=build_combinations(),
    )

    assert result.available is False
    assert result.recommended is None


def test_rejects_when_two_reservations_block_combination():
    engine = ReservationReoptimizer()

    reservations = [
        ExistingReservation(
            id="reservation-1",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=120),
            party_size=2,
            table_ids=("table-1",),
        ),
        ExistingReservation(
            id="reservation-2",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=120),
            party_size=4,
            table_ids=("table-2",),
        ),
    ]

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=6,
            duration_minutes=120,
        ),
        tables=build_tables(),
        reservations=reservations,
        combinations=build_combinations(),
    )

    assert result.available is False
    assert result.recommended is None

def test_live_locked_reservation_blocks_table_after_expected_end():
    engine = ReservationReoptimizer()

    seated = ExistingReservation(
        id="reservation-seated",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=("table-1",),
        status="seated",
        locked=True,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW + timedelta(minutes=90),
            party_size=2,
            duration_minutes=90,
        ),
        tables=build_tables(),
        reservations=[seated],
        combinations=[],
    )

    assert result.available is True
    assert result.recommended is not None
    assert (
        "table-1"
        not in result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
    )


def test_confirmed_expected_turn_allows_normal_back_to_back_planning():
    engine = ReservationReoptimizer()

    confirmed = ExistingReservation(
        id="reservation-confirmed",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=("table-1",),
        status="confirmed",
        locked=False,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW + timedelta(minutes=90),
            party_size=2,
            duration_minutes=90,
        ),
        tables=build_tables(),
        reservations=[confirmed],
        combinations=[],
    )

    assert result.available is True
    assert result.recommended is not None
    assert (
        result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
        == ("table-1",)
    )

def test_live_seated_multi_table_blocks_any_candidate_using_occupied_table():
    engine = ReservationReoptimizer()

    seated = ExistingReservation(
        id="reservation-seated-combination",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=6,
        table_ids=("table-1", "table-2"),
        status="seated",
        locked=True,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW + timedelta(minutes=90),
            party_size=2,
            duration_minutes=90,
        ),
        tables=build_tables(),
        reservations=[seated],
        combinations=build_combinations(),
    )

    assert result.available is True
    assert result.recommended is not None

    assigned_table_ids = set(
        result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
    )

    assert assigned_table_ids == {"table-3"}
    assert assigned_table_ids.isdisjoint(
        {"table-1", "table-2"},
    )

def test_live_seated_occupancy_returns_no_safe_plan_when_no_alternative_exists():
    engine = ReservationReoptimizer()

    seated = ExistingReservation(
        id="reservation-seated",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=("table-1",),
        status="seated",
        locked=True,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW + timedelta(minutes=90),
            party_size=2,
            duration_minutes=90,
        ),
        tables=[build_tables()[0]],
        reservations=[seated],
        combinations=[],
    )

    assert result.available is False
    assert result.recommended is None
    assert result.alternatives == ()

def test_completed_reservation_releases_table_for_live_reoptimization():
    engine = ReservationReoptimizer()

    completed = ExistingReservation(
        id="reservation-completed",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=("table-1",),
        status="completed",
        locked=False,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW + timedelta(minutes=90),
            party_size=2,
            duration_minutes=90,
        ),
        tables=build_tables(),
        reservations=[completed],
        combinations=[],
    )

    assert result.available is True
    assert result.recommended is not None
    assert (
        result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
        == ("table-1",)
    )


def test_no_show_reservation_releases_table_for_live_reoptimization():
    engine = ReservationReoptimizer()

    no_show = ExistingReservation(
        id="reservation-no-show",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=("table-1",),
        status="no_show",
        locked=False,
    )

    result = engine.reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW + timedelta(minutes=90),
            party_size=2,
            duration_minutes=90,
        ),
        tables=build_tables(),
        reservations=[no_show],
        combinations=[],
    )

    assert result.available is True
    assert result.recommended is not None
    assert (
        result.recommended
        .new_reservation_assignment
        .candidate
        .table_ids
        == ("table-1",)
    )

def test_gap_recovery_requires_two_coordinated_moves():
    """Recover a booking only when two existing assignments are moved."""
    tables = [
        IntelligenceTable(
            id=f"table-{number}",
            table_number=str(number),
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        )
        for number in range(1, 5)
    ]

    combinations = [
        TableCombination(
            id="combination-1-2",
            name="Tables 1 + 2",
            table_ids=("table-1", "table-2"),
            min_capacity=3,
            max_capacity=4,
            setup_minutes=0,
        ),
    ]

    reservations = [
        ExistingReservation(
            id="reservation-A",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-1",),
        ),
        ExistingReservation(
            id="reservation-B",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-2",),
        ),
    ]

    engine = ReservationReoptimizer()

    def run(limit):
        return engine.reoptimize(
            request=ReoptimizationRequest(
                requested_start=NOW,
                party_size=4,
                duration_minutes=90,
                max_reservations_to_move=limit,
            ),
            tables=tables,
            reservations=reservations,
            combinations=combinations,
        )

    restricted = run(1)

    assert restricted.available is False
    assert restricted.recommended is None

    recovered = run(2)

    assert recovered.available is True
    assert recovered.recommended is not None

    plan = recovered.recommended

    assert plan.moved_reservations_count == 2
    assert len(plan.moves) == 2

    assert {
        move.reservation_id for move in plan.moves
    } == {"reservation-A", "reservation-B"}

    assert (
        plan.new_reservation_assignment.candidate.table_ids
        == ("table-1", "table-2")
    )

    assert {
        table_id
        for move in plan.moves
        for table_id in move.to_table_ids
    } == {"table-3", "table-4"}

    for move in plan.moves:
        assert move.start_at == NOW
        assert move.end_at == NOW + timedelta(minutes=90)


def test_gap_recovery_never_moves_seated_reservations():
    tables = [
        IntelligenceTable(
            id=f"table-{number}",
            table_number=str(number),
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        )
        for number in range(1, 5)
    ]

    combinations = [
        TableCombination(
            id="combination-1-2",
            name="Tables 1 + 2",
            table_ids=("table-1", "table-2"),
            min_capacity=3,
            max_capacity=4,
        ),
    ]

    reservations = [
        ExistingReservation(
            id="seated-guest",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-1",),
            status="seated",
            locked=False,
        ),
        ExistingReservation(
            id="confirmed-guest",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-2",),
            status="confirmed",
            locked=False,
        ),
    ]

    result = ReservationReoptimizer().reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=4,
            duration_minutes=90,
            max_reservations_to_move=2,
        ),
        tables=tables,
        reservations=reservations,
        combinations=combinations,
    )

    assert result.available is False
    assert result.recommended is None


def test_two_move_recovery_rejects_conflicting_destinations():
    """Two moved reservations cannot occupy the same destination."""
    tables = [
        IntelligenceTable(
            id=f"table-{number}",
            table_number=str(number),
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        )
        for number in range(1, 4)
    ]

    combinations = [
        TableCombination(
            id="combination-1-2",
            name="Tables 1 + 2",
            table_ids=("table-1", "table-2"),
            min_capacity=3,
            max_capacity=4,
        ),
    ]

    reservations = [
        ExistingReservation(
            id=f"reservation-{number}",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=(f"table-{number}",),
        )
        for number in (1, 2)
    ]

    result = ReservationReoptimizer().reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=4,
            duration_minutes=90,
            max_reservations_to_move=2,
        ),
        tables=tables,
        reservations=reservations,
        combinations=combinations,
    )

    assert result.available is False
    assert result.recommended is None


def test_two_move_recovery_respects_preparation_buffer():
    """Recovery must not bypass the preparation buffer."""
    tables = [
        IntelligenceTable(
            id=f"table-{number}",
            table_number=str(number),
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        )
        for number in range(1, 5)
    ]

    combinations = [
        TableCombination(
            id="combination-1-2",
            name="Tables 1 + 2",
            table_ids=("table-1", "table-2"),
            min_capacity=3,
            max_capacity=4,
        ),
    ]

    reservations = [
        ExistingReservation(
            id="reservation-A",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-1",),
        ),
        ExistingReservation(
            id="reservation-B",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-2",),
        ),
        ExistingReservation(
            id="reservation-C",
            start_at=NOW - timedelta(minutes=90),
            end_at=NOW,
            party_size=2,
            table_ids=("table-3",),
            locked=True,
        ),
        ExistingReservation(
            id="reservation-D",
            start_at=NOW - timedelta(minutes=90),
            end_at=NOW,
            party_size=2,
            table_ids=("table-4",),
            locked=True,
        ),
    ]

    result = ReservationReoptimizer().reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=4,
            duration_minutes=90,
            buffer_before_minutes=15,
            max_reservations_to_move=2,
        ),
        tables=tables,
        reservations=reservations,
        combinations=combinations,
    )

    assert result.available is False
    assert result.recommended is None


def test_gap_recovery_two_moves_cannot_be_autopilot_authorized():
    """Two-move plans require manager approval even if marked eligible."""
    from uuid import uuid4

    from app.intelligence_execution.autopilot import (
        AutopilotAuthorityService,
    )

    from app.intelligence_execution.schemas import (
        ExecutionEligibility,
        ExecutionEligibilityResult,
    )

    eligibility = ExecutionEligibilityResult(
        restaurant_id=uuid4(),
        eligibility=ExecutionEligibility.ELIGIBLE_FOR_AUTOMATIC_EXECUTION,
        generated_at=NOW,
    )

    authority = AutopilotAuthorityService()

    plan = {
        "moves": [
            {"reservation_id": str(uuid4())},
            {"reservation_id": str(uuid4())},
        ],
        "execution_eligibility": eligibility.model_dump(mode="json"),
    }

    assert authority.can_execute_stored_plan_automatically(
        plan=plan,
        autopilot_enabled=True,
    ) is False

    plan["moves"] = plan["moves"][:1]

    assert authority.can_execute_stored_plan_automatically(
        plan=plan,
        autopilot_enabled=True,
    ) is True


def test_gap_recovery_v2_preserves_locked_special_request():
    """A protected reservation cannot be moved by Gap Recovery V2."""
    tables = [
        IntelligenceTable(
            id=f"table-{i}",
            table_number=str(i),
            min_capacity=1,
            max_capacity=2,
            area_id="main",
        )
        for i in range(1, 5)
    ]

    combinations = [
        TableCombination(
            id="combination-1-2",
            name="Tables 1 + 2",
            table_ids=("table-1", "table-2"),
            min_capacity=3,
            max_capacity=4,
        ),
    ]

    reservations = [
        ExistingReservation(
            id="special-request",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-1",),
            status="confirmed",
            locked=True,
        ),
        ExistingReservation(
            id="ordinary-reservation",
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            party_size=2,
            table_ids=("table-2",),
            status="confirmed",
            locked=False,
        ),
    ]

    result = ReservationReoptimizer().reoptimize(
        request=ReoptimizationRequest(
            requested_start=NOW,
            party_size=4,
            duration_minutes=90,
            max_reservations_to_move=2,
        ),
        tables=tables,
        reservations=reservations,
        combinations=combinations,
    )

    assert result.available is False
    assert result.recommended is None
