from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.intelligence_temporal.calibration_metrics import (
    TemporalCalibrationMetricsService,
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
    signed_error_minutes: int,
) -> TemporalTurnPredictionOutcome:
    predicted_duration_minutes = 100

    actual_duration_minutes = (
        predicted_duration_minutes
        + signed_error_minutes
    )

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
            actual_duration_minutes
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


def test_empty_dataset_returns_no_averages_or_rates():
    metrics = (
        TemporalCalibrationMetricsService
        .calculate([])
    )

    assert metrics.sample_count == 0

    assert (
        metrics.mean_absolute_error_minutes
        is None
    )

    assert (
        metrics.mean_signed_error_minutes
        is None
    )

    assert metrics.underprediction_count == 0
    assert metrics.underprediction_rate is None

    assert metrics.overprediction_count == 0
    assert metrics.overprediction_rate is None

    assert metrics.exact_count == 0
    assert metrics.exact_rate is None

    assert metrics.within_5_minutes_count == 0
    assert metrics.within_5_minutes_rate is None

    assert metrics.within_10_minutes_count == 0
    assert metrics.within_10_minutes_rate is None


def test_exact_prediction_is_counted_correctly():
    metrics = (
        TemporalCalibrationMetricsService
        .calculate(
            [
                _outcome(
                    signed_error_minutes=0,
                )
            ]
        )
    )

    assert metrics.sample_count == 1
    assert metrics.mean_absolute_error_minutes == 0
    assert metrics.mean_signed_error_minutes == 0

    assert metrics.underprediction_count == 0
    assert metrics.overprediction_count == 0

    assert metrics.exact_count == 1
    assert metrics.exact_rate == 1

    assert metrics.within_5_minutes_count == 1
    assert metrics.within_5_minutes_rate == 1

    assert metrics.within_10_minutes_count == 1
    assert metrics.within_10_minutes_rate == 1


def test_underprediction_is_positive_signed_error():
    metrics = (
        TemporalCalibrationMetricsService
        .calculate(
            [
                _outcome(
                    signed_error_minutes=12,
                )
            ]
        )
    )

    assert metrics.mean_absolute_error_minutes == 12
    assert metrics.mean_signed_error_minutes == 12

    assert metrics.underprediction_count == 1
    assert metrics.underprediction_rate == 1

    assert metrics.overprediction_count == 0
    assert metrics.overprediction_rate == 0

    assert metrics.exact_count == 0
    assert metrics.exact_rate == 0


def test_overprediction_is_negative_signed_error():
    metrics = (
        TemporalCalibrationMetricsService
        .calculate(
            [
                _outcome(
                    signed_error_minutes=-8,
                )
            ]
        )
    )

    assert metrics.mean_absolute_error_minutes == 8
    assert metrics.mean_signed_error_minutes == -8

    assert metrics.underprediction_count == 0
    assert metrics.underprediction_rate == 0

    assert metrics.overprediction_count == 1
    assert metrics.overprediction_rate == 1

    assert metrics.exact_count == 0
    assert metrics.exact_rate == 0


def test_mixed_dataset_calculates_mean_errors():
    outcomes = [
        _outcome(
            signed_error_minutes=10,
        ),
        _outcome(
            signed_error_minutes=-5,
        ),
        _outcome(
            signed_error_minutes=0,
        ),
        _outcome(
            signed_error_minutes=15,
        ),
    ]

    metrics = (
        TemporalCalibrationMetricsService
        .calculate(outcomes)
    )

    assert metrics.sample_count == 4

    assert (
        metrics.mean_absolute_error_minutes
        == 7.5
    )

    assert (
        metrics.mean_signed_error_minutes
        == 5
    )

    assert metrics.underprediction_count == 2
    assert metrics.underprediction_rate == 0.5

    assert metrics.overprediction_count == 1
    assert metrics.overprediction_rate == 0.25

    assert metrics.exact_count == 1
    assert metrics.exact_rate == 0.25


def test_within_five_minutes_is_inclusive():
    outcomes = [
        _outcome(
            signed_error_minutes=5,
        ),
        _outcome(
            signed_error_minutes=-5,
        ),
        _outcome(
            signed_error_minutes=6,
        ),
    ]

    metrics = (
        TemporalCalibrationMetricsService
        .calculate(outcomes)
    )

    assert metrics.within_5_minutes_count == 2

    assert (
        metrics.within_5_minutes_rate
        == 2 / 3
    )


def test_within_ten_minutes_is_inclusive():
    outcomes = [
        _outcome(
            signed_error_minutes=10,
        ),
        _outcome(
            signed_error_minutes=-10,
        ),
        _outcome(
            signed_error_minutes=11,
        ),
    ]

    metrics = (
        TemporalCalibrationMetricsService
        .calculate(outcomes)
    )

    assert metrics.within_10_minutes_count == 2

    assert (
        metrics.within_10_minutes_rate
        == 2 / 3
    )


def test_five_minute_matches_are_also_within_ten():
    outcomes = [
        _outcome(
            signed_error_minutes=3,
        ),
        _outcome(
            signed_error_minutes=-7,
        ),
        _outcome(
            signed_error_minutes=14,
        ),
    ]

    metrics = (
        TemporalCalibrationMetricsService
        .calculate(outcomes)
    )

    assert metrics.within_5_minutes_count == 1
    assert metrics.within_10_minutes_count == 2

    assert (
        metrics.within_5_minutes_rate
        == 1 / 3
    )

    assert (
        metrics.within_10_minutes_rate
        == 2 / 3
    )