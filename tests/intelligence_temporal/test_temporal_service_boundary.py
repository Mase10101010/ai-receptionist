from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import pytest

from app.intelligence.optimizer import (
    ReservationOptimizer,
)
from app.intelligence.types import (
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


def _tables():
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


def _technical_result():
    return ReservationOptimizer().optimize(
        request=OptimizationRequest(
            requested_start=NOW,
            party_size=4,
            duration_minutes=90,
            max_alternatives=2,
        ),
        tables=_tables(),
        reservations=[],
        combinations=[],
    )


def test_production_temporal_inputs_are_compatible():
    technical = _technical_result()

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                FutureCapacityRequest(
                    restaurant_id=(
                        RESTAURANT_ID
                    ),
                    start_at=NOW,
                    party_size=4,
                    duration_minutes=90,
                )
            ),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=4,
        )
    )

    assert result.available is True
    assert result.recommended is not None

    assert result.evaluated_candidates == (
        1 + len(technical.alternatives)
    )


def test_temporal_result_preserves_candidate_set():
    technical = _technical_result()

    temporal = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=technical,
            capacity_request=(
                FutureCapacityRequest(
                    restaurant_id=(
                        RESTAURANT_ID
                    ),
                    start_at=NOW,
                    party_size=4,
                    duration_minutes=90,
                )
            ),
            reservations=[],
            tables=_tables(),
            combinations=[],
            candidate_party_size=4,
        )
    )

    technical_ids = {
        tuple(
            candidate.candidate.table_ids
        )
        for candidate in [
            technical.recommended,
            *technical.alternatives,
        ]
        if candidate is not None
    }

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

    assert temporal_ids == technical_ids


def test_temporal_result_does_not_mutate_scores():
    technical = _technical_result()

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
                FutureCapacityRequest(
                    restaurant_id=(
                        RESTAURANT_ID
                    ),
                    start_at=NOW,
                    party_size=4,
                    duration_minutes=90,
                )
            ),
            reservations=[],
            tables=_tables(),
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