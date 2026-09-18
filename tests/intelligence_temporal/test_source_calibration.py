from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionOutcome,
)
from app.intelligence_temporal.source_calibration import (
    TemporalSourceCalibrationService,
)


def _outcome(
    *,
    source: ExpectedTurnSource,
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
        source=source,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=(
            source
            != ExpectedTurnSource.PLANNED_FALLBACK
        ),
    )


def test_empty_dataset_preserves_all_source_buckets():
    snapshot = (
        TemporalSourceCalibrationService
        .calculate([])
    )

    assert len(snapshot.sources) == len(
        ExpectedTurnSource
    )

    for source in ExpectedTurnSource:
        calibration = snapshot.for_source(source)

        assert calibration.source == source
        assert calibration.metrics.sample_count == 0
        assert (
            calibration.metrics
            .mean_absolute_error_minutes
            is None
        )


def test_groups_outcomes_by_prediction_source():
    outcomes = [
        _outcome(
            source=ExpectedTurnSource.PARTY_SIZE,
            signed_error_minutes=4,
        ),
        _outcome(
            source=ExpectedTurnSource.DAYPART,
            signed_error_minutes=12,
        ),
        _outcome(
            source=ExpectedTurnSource.SERVICE_AREA,
            signed_error_minutes=-6,
        ),
    ]

    snapshot = (
        TemporalSourceCalibrationService
        .calculate(outcomes)
    )

    assert (
        snapshot.for_source(
            ExpectedTurnSource.PARTY_SIZE
        ).metrics.mean_absolute_error_minutes
        == 4
    )

    assert (
        snapshot.for_source(
            ExpectedTurnSource.DAYPART
        ).metrics.mean_absolute_error_minutes
        == 12
    )

    assert (
        snapshot.for_source(
            ExpectedTurnSource.SERVICE_AREA
        ).metrics.mean_absolute_error_minutes
        == 6
    )


def test_multiple_outcomes_aggregate_inside_same_source():
    outcomes = [
        _outcome(
            source=ExpectedTurnSource.PARTY_SIZE,
            signed_error_minutes=5,
        ),
        _outcome(
            source=ExpectedTurnSource.PARTY_SIZE,
            signed_error_minutes=-7,
        ),
        _outcome(
            source=ExpectedTurnSource.PARTY_SIZE,
            signed_error_minutes=0,
        ),
    ]

    snapshot = (
        TemporalSourceCalibrationService
        .calculate(outcomes)
    )

    metrics = snapshot.for_source(
        ExpectedTurnSource.PARTY_SIZE
    ).metrics

    assert metrics.sample_count == 3
    assert (
        metrics.mean_absolute_error_minutes
        == 4
    )
    assert (
        metrics.mean_signed_error_minutes
        == -2 / 3
    )

    assert metrics.underprediction_count == 1
    assert metrics.overprediction_count == 1
    assert metrics.exact_count == 1


def test_source_buckets_do_not_leak():
    outcomes = [
        _outcome(
            source=ExpectedTurnSource.RESTAURANT,
            signed_error_minutes=20,
        ),
        _outcome(
            source=ExpectedTurnSource.DAY_OF_WEEK,
            signed_error_minutes=3,
        ),
        _outcome(
            source=ExpectedTurnSource.DAY_OF_WEEK,
            signed_error_minutes=-5,
        ),
    ]

    snapshot = (
        TemporalSourceCalibrationService
        .calculate(outcomes)
    )

    assert (
        snapshot.for_source(
            ExpectedTurnSource.RESTAURANT
        ).metrics.sample_count
        == 1
    )

    assert (
        snapshot.for_source(
            ExpectedTurnSource.DAY_OF_WEEK
        ).metrics.sample_count
        == 2
    )

    assert (
        snapshot.for_source(
            ExpectedTurnSource.DAYPART
        ).metrics.sample_count
        == 0
    )


def test_planned_fallback_is_measured_as_its_own_source():
    outcome = _outcome(
        source=ExpectedTurnSource.PLANNED_FALLBACK,
        signed_error_minutes=9,
    )

    snapshot = (
        TemporalSourceCalibrationService
        .calculate([outcome])
    )

    metrics = snapshot.for_source(
        ExpectedTurnSource.PLANNED_FALLBACK
    ).metrics

    assert metrics.sample_count == 1
    assert metrics.mean_absolute_error_minutes == 9
    assert metrics.mean_signed_error_minutes == 9


def test_unknown_source_lookup_fails_explicitly():
    snapshot = (
        TemporalSourceCalibrationService
        .calculate([])
    )

    with pytest.raises(KeyError):
        snapshot.for_source("unknown")  # type: ignore[arg-type]