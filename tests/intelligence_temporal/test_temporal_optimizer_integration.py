from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.intelligence.optimizer import ReservationOptimizer
from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    OptimizationRequest,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
)
from app.intelligence_temporal.temporal_optimization import (
    TemporalOptimizationOrchestrator,
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
TABLE_3 = uuid4()


def _table(
    table_id,
    number: str,
    *,
    capacity: int = 4,
) -> IntelligenceTable:
    return IntelligenceTable(
        id=str(table_id),
        table_number=number,
        min_capacity=1,
        max_capacity=capacity,
        area_id="main",
        floor_id=None,
        active=True,
    )


def _technical_request(
    *,
    party_size: int = 4,
    duration_minutes: int = 90,
    max_alternatives: int = 5,
) -> OptimizationRequest:
    return OptimizationRequest(
        requested_start=NOW,
        party_size=party_size,
        duration_minutes=duration_minutes,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        preferred_area_id=None,
        preferred_floor_id=None,
        allow_combinations=True,
        max_alternatives=max_alternatives,
    )


def _capacity_request(
    *,
    party_size: int = 4,
    duration_minutes: int = 30,
    horizon_minutes: int = 120,
) -> FutureCapacityRequest:
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=party_size,
        duration_minutes=duration_minutes,
        horizon_minutes=horizon_minutes,
        slot_minutes=30,
    )


def test_real_optimizer_candidates_flow_into_temporal_ranking():
    tables = [
        _table(TABLE_1, "1"),
        _table(TABLE_2, "2"),
        _table(TABLE_3, "3"),
    ]

    reservations: list[
        ExistingReservation
    ] = []

    technical = ReservationOptimizer().optimize(
        request=_technical_request(),
        tables=tables,
        reservations=reservations,
        combinations=[],
    )

    assert technical.available is True
    assert technical.recommended is not None

    temporal = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                _capacity_request()
            ),
            reservations=reservations,
            tables=tables,
            combinations=[],
            candidate_party_size=4,
        )
    )

    assert temporal.available is True

    assert temporal.evaluated_candidates == (
        1 + len(technical.alternatives)
    )

    assert temporal.recommended is not None


def test_temporal_layer_only_evaluates_accepted_optimizer_candidates():
    tables = [
        _table(TABLE_1, "1"),
        _table(TABLE_2, "2"),
    ]

    blocked = ExistingReservation(
        id="blocked-table-1",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=4,
        table_ids=(str(TABLE_1),),
        status="confirmed",
        locked=False,
    )

    reservations = [blocked]

    technical = ReservationOptimizer().optimize(
        request=_technical_request(),
        tables=tables,
        reservations=reservations,
        combinations=[],
    )

    assert technical.available is True
    assert technical.recommended is not None

    accepted = [
        technical.recommended,
        *technical.alternatives,
    ]

    assert all(
        str(TABLE_1)
        not in candidate.candidate.table_ids
        for candidate in accepted
    )

    temporal = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                _capacity_request()
            ),
            reservations=reservations,
            tables=tables,
            combinations=[],
            candidate_party_size=4,
        )
    )

    assert temporal.available is True

    assert all(
        TABLE_1
        not in ranked.evaluation.candidate.table_ids
        for ranked in [
            temporal.recommended,
            *temporal.alternatives,
        ]
        if ranked is not None
    )


def test_temporal_ranking_preserves_original_candidate_identity():
    tables = [
        _table(TABLE_1, "1"),
        _table(TABLE_2, "2"),
    ]

    technical = ReservationOptimizer().optimize(
        request=_technical_request(),
        tables=tables,
        reservations=[],
        combinations=[],
    )

    accepted_ids = {
        tuple(
            candidate.candidate.table_ids
        )
        for candidate in [
            technical.recommended,
            *technical.alternatives,
        ]
        if candidate is not None
    }

    temporal = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                _capacity_request()
            ),
            reservations=[],
            tables=tables,
            combinations=[],
            candidate_party_size=4,
        )
    )

    temporal_ids = {
        tuple(
            str(table_id)
            for table_id in (
                ranked
                .evaluation
                .candidate
                .table_ids
            )
        )
        for ranked in [
            temporal.recommended,
            *temporal.alternatives,
        ]
        if ranked is not None
    }

    assert temporal_ids == accepted_ids


def test_temporal_layer_does_not_mutate_optimizer_scores():
    tables = [
        _table(TABLE_1, "1"),
        _table(TABLE_2, "2"),
    ]

    technical = ReservationOptimizer().optimize(
        request=_technical_request(),
        tables=tables,
        reservations=[],
        combinations=[],
    )

    before = [
        candidate.score
        for candidate in [
            technical.recommended,
            *technical.alternatives,
        ]
        if candidate is not None
    ]

    (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                _capacity_request()
            ),
            reservations=[],
            tables=tables,
            combinations=[],
            candidate_party_size=4,
        )
    )

    after = [
        candidate.score
        for candidate in [
            technical.recommended,
            *technical.alternatives,
        ]
        if candidate is not None
    ]

    assert after == before


def test_temporal_layer_preserves_unavailable_truth():
    tables = [
        _table(TABLE_1, "1"),
    ]

    blocked = ExistingReservation(
        id="blocked",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=4,
        table_ids=(str(TABLE_1),),
        status="confirmed",
        locked=False,
    )

    technical = ReservationOptimizer().optimize(
        request=_technical_request(),
        tables=tables,
        reservations=[blocked],
        combinations=[],
    )

    assert technical.available is False
    assert technical.recommended is None

    temporal = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                _capacity_request()
            ),
            reservations=[blocked],
            tables=tables,
            combinations=[],
            candidate_party_size=4,
        )
    )

    assert temporal.available is False
    assert temporal.recommended is None
    assert temporal.evaluated_candidates == 0


def test_temporal_result_preserves_technical_order_for_audit():
    tables = [
        _table(TABLE_1, "1"),
        _table(TABLE_2, "2"),
        _table(TABLE_3, "3"),
    ]

    technical = ReservationOptimizer().optimize(
        request=_technical_request(),
        tables=tables,
        reservations=[],
        combinations=[],
    )

    expected_scores = [
        candidate.score
        for candidate in [
            technical.recommended,
            *technical.alternatives,
        ]
        if candidate is not None
    ]

    temporal = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                _capacity_request()
            ),
            reservations=[],
            tables=tables,
            combinations=[],
            candidate_party_size=4,
        )
    )

    assert (
        temporal.technical_candidate_order
        == expected_scores
    )