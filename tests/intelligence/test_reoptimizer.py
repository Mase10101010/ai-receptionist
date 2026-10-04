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