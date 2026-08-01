from datetime import datetime

from app.intelligence.optimizer import ReservationOptimizer
from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    OptimizationRequest,
    TableCombination,
)


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 1, hour, minute)


def test_optimizer_prefers_exact_capacity_fit() -> None:
    optimizer = ReservationOptimizer()

    result = optimizer.optimize(
        request=OptimizationRequest(
            requested_start=dt(19),
            party_size=2,
            duration_minutes=90,
        ),
        tables=[
            IntelligenceTable(
                id="t2",
                table_number="2",
                min_capacity=1,
                max_capacity=2,
            ),
            IntelligenceTable(
                id="t4",
                table_number="4",
                min_capacity=1,
                max_capacity=4,
            ),
        ],
        reservations=[],
    )

    assert result.available is True
    assert result.recommended is not None
    assert result.recommended.candidate.table_ids == ("t2",)


def test_optimizer_uses_gap_when_duration_fits_exactly() -> None:
    optimizer = ReservationOptimizer()

    result = optimizer.optimize(
        request=OptimizationRequest(
            requested_start=dt(19, 30),
            party_size=2,
            duration_minutes=60,
        ),
        tables=[
            IntelligenceTable(
                id="t1",
                table_number="1",
                min_capacity=1,
                max_capacity=2,
            ),
        ],
        reservations=[
            ExistingReservation(
                id="r1",
                start_at=dt(18),
                end_at=dt(19, 30),
                party_size=2,
                table_ids=("t1",),
            ),
            ExistingReservation(
                id="r2",
                start_at=dt(20, 30),
                end_at=dt(22),
                party_size=2,
                table_ids=("t1",),
            ),
        ],
    )

    assert result.available is True
    assert result.recommended is not None
    assert result.recommended.candidate.table_ids == ("t1",)


def test_optimizer_rejects_gap_when_duration_does_not_fit() -> None:
    optimizer = ReservationOptimizer()

    result = optimizer.optimize(
        request=OptimizationRequest(
            requested_start=dt(19, 30),
            party_size=2,
            duration_minutes=90,
        ),
        tables=[
            IntelligenceTable(
                id="t1",
                table_number="1",
                min_capacity=1,
                max_capacity=2,
            ),
        ],
        reservations=[
            ExistingReservation(
                id="r2",
                start_at=dt(20, 30),
                end_at=dt(22),
                party_size=2,
                table_ids=("t1",),
            ),
        ],
    )

    assert result.available is False


def test_optimizer_can_use_configured_combination() -> None:
    optimizer = ReservationOptimizer()

    result = optimizer.optimize(
        request=OptimizationRequest(
            requested_start=dt(19),
            party_size=6,
            duration_minutes=90,
        ),
        tables=[
            IntelligenceTable(
                id="t1",
                table_number="1",
                min_capacity=1,
                max_capacity=4,
                area_id="main",
                floor_id="ground",
            ),
            IntelligenceTable(
                id="t2",
                table_number="2",
                min_capacity=1,
                max_capacity=4,
                area_id="main",
                floor_id="ground",
            ),
        ],
        reservations=[],
        combinations=[
            TableCombination(
                id="c1",
                name="T1 + T2",
                table_ids=("t1", "t2"),
                min_capacity=5,
                max_capacity=8,
                setup_minutes=5,
            ),
        ],
    )

    assert result.available is True
    assert result.recommended is not None
    assert result.recommended.candidate.table_ids == ("t1", "t2")
