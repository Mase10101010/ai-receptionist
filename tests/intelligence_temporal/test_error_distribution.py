from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.intelligence_temporal.error_distribution import (
    TemporalErrorDistributionService,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionOutcome,
)


def _outcome(
    signed_error_minutes: int,
) -> TemporalTurnPredictionOutcome:
    predicted_duration_minutes = 100

    return TemporalTurnPredictionOutcome(
        reservation_id=uuid4(),
        restaurant_id=uuid4(),
        predicted_at=datetime(
            2026,
            9,
            6,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            9,
            6,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        predicted_duration_minutes=(
            predicted_duration_minutes
        ),
        actual_duration_minutes=(
            predicted_duration_minutes
            + signed_error_minutes
        ),
        signed_error_minutes=(
            signed_error_minutes
        ),
        absolute_error_minutes=abs(
            signed_error_minutes
        ),
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


def test_empty_distribution_has_no_quantiles():
    distribution = (
        TemporalErrorDistributionService
        .calculate([])
    )

    assert distribution.sample_count == 0

    assert (
        distribution.p10_signed_error_minutes
        is None
    )

    assert (
        distribution.p50_signed_error_minutes
        is None
    )

    assert (
        distribution.p90_signed_error_minutes
        is None
    )


def test_calculates_empirical_signed_error_quantiles():
    outcomes = [
        _outcome(error)
        for error in [
            -20,
            -15,
            -10,
            -5,
            0,
            5,
            10,
            15,
            20,
            25,
        ]
    ]

    distribution = (
        TemporalErrorDistributionService
        .calculate(outcomes)
    )

    assert distribution.sample_count == 10

    assert (
        distribution.p10_signed_error_minutes
        == -20
    )

    assert (
        distribution.p50_signed_error_minutes
        == 0
    )

    assert (
        distribution.p90_signed_error_minutes
        == 20
    )


def test_distribution_preserves_directional_error():
    outcomes = [
        _outcome(error)
        for error in [
            5,
            6,
            7,
            8,
            9,
        ]
    ]

    distribution = (
        TemporalErrorDistributionService
        .calculate(outcomes)
    )

    assert (
        distribution.p10_signed_error_minutes
        == 5
    )

    assert (
        distribution.p50_signed_error_minutes
        == 7
    )

    assert (
        distribution.p90_signed_error_minutes
        == 9
    )


def test_negative_distribution_preserves_overprediction():
    outcomes = [
        _outcome(error)
        for error in [
            -20,
            -15,
            -10,
            -5,
            -1,
        ]
    ]

    distribution = (
        TemporalErrorDistributionService
        .calculate(outcomes)
    )

    assert (
        distribution.p10_signed_error_minutes
        == -20
    )

    assert (
        distribution.p50_signed_error_minutes
        == -10
    )

    assert (
        distribution.p90_signed_error_minutes
        == -1
    )


def test_quantiles_are_order_independent():
    first = [
        _outcome(error)
        for error in [
            -10,
            0,
            10,
            20,
            30,
        ]
    ]

    second = list(reversed(first))

    first_distribution = (
        TemporalErrorDistributionService
        .calculate(first)
    )

    second_distribution = (
        TemporalErrorDistributionService
        .calculate(second)
    )

    assert (
        first_distribution
        == second_distribution
    )


def test_single_sample_remains_deterministic():
    distribution = (
        TemporalErrorDistributionService
        .calculate(
            [_outcome(12)]
        )
    )

    assert distribution.sample_count == 1

    assert (
        distribution.p10_signed_error_minutes
        == 12
    )

    assert (
        distribution.p50_signed_error_minutes
        == 12
    )

    assert (
        distribution.p90_signed_error_minutes
        == 12
    )