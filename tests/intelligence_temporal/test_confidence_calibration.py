from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.intelligence_temporal.confidence_calibration import (
    TemporalConfidenceCalibrationService,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionOutcome,
)


def _outcome(
    *,
    confidence: ExpectedTurnConfidence,
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
            19,
            40,
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
        confidence=confidence,
        used_learned_pattern=True,
    )


def test_empty_dataset_returns_empty_metrics_for_all_confidence_levels():
    snapshot = (
        TemporalConfidenceCalibrationService
        .calculate([])
    )

    assert snapshot.low.metrics.sample_count == 0
    assert snapshot.medium.metrics.sample_count == 0
    assert snapshot.high.metrics.sample_count == 0

    assert (
        snapshot.low.metrics
        .mean_absolute_error_minutes
        is None
    )

    assert (
        snapshot.medium.metrics
        .mean_absolute_error_minutes
        is None
    )

    assert (
        snapshot.high.metrics
        .mean_absolute_error_minutes
        is None
    )


def test_groups_outcomes_by_confidence():
    outcomes = [
        _outcome(
            confidence=ExpectedTurnConfidence.LOW,
            signed_error_minutes=20,
        ),
        _outcome(
            confidence=ExpectedTurnConfidence.MEDIUM,
            signed_error_minutes=10,
        ),
        _outcome(
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=5,
        ),
    ]

    snapshot = (
        TemporalConfidenceCalibrationService
        .calculate(outcomes)
    )

    assert snapshot.low.metrics.sample_count == 1
    assert snapshot.medium.metrics.sample_count == 1
    assert snapshot.high.metrics.sample_count == 1

    assert (
        snapshot.low.metrics
        .mean_absolute_error_minutes
        == 20
    )

    assert (
        snapshot.medium.metrics
        .mean_absolute_error_minutes
        == 10
    )

    assert (
        snapshot.high.metrics
        .mean_absolute_error_minutes
        == 5
    )


def test_multiple_outcomes_are_aggregated_inside_same_confidence_bucket():
    outcomes = [
        _outcome(
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=4,
        ),
        _outcome(
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=-6,
        ),
        _outcome(
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=0,
        ),
    ]

    snapshot = (
        TemporalConfidenceCalibrationService
        .calculate(outcomes)
    )

    metrics = snapshot.high.metrics

    assert metrics.sample_count == 3

    assert (
        metrics.mean_absolute_error_minutes
        == 10 / 3
    )

    assert (
        metrics.mean_signed_error_minutes
        == -2 / 3
    )

    assert metrics.underprediction_count == 1
    assert metrics.overprediction_count == 1
    assert metrics.exact_count == 1


def test_confidence_buckets_do_not_leak_into_each_other():
    outcomes = [
        _outcome(
            confidence=ExpectedTurnConfidence.LOW,
            signed_error_minutes=25,
        ),
        _outcome(
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=2,
        ),
        _outcome(
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=-3,
        ),
    ]

    snapshot = (
        TemporalConfidenceCalibrationService
        .calculate(outcomes)
    )

    assert snapshot.low.metrics.sample_count == 1
    assert snapshot.medium.metrics.sample_count == 0
    assert snapshot.high.metrics.sample_count == 2

    assert (
        snapshot.low.metrics
        .mean_absolute_error_minutes
        == 25
    )

    assert (
        snapshot.high.metrics
        .mean_absolute_error_minutes
        == 2.5
    )


def test_snapshot_preserves_confidence_identity():
    snapshot = (
        TemporalConfidenceCalibrationService
        .calculate([])
    )

    assert (
        snapshot.low.confidence
        == ExpectedTurnConfidence.LOW
    )

    assert (
        snapshot.medium.confidence
        == ExpectedTurnConfidence.MEDIUM
    )

    assert (
        snapshot.high.confidence
        == ExpectedTurnConfidence.HIGH
    )