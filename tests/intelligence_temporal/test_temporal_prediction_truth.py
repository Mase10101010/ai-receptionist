from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.intelligence_temporal.observations import (
    TemporalTurnObservation,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnPrediction,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalPredictionTruthService,
)


def _prediction(
    *,
    expected=100,
):
    return ExpectedTurnPrediction(
        expected_duration_minutes=expected,
        planned_duration_minutes=90,
        adjustment_minutes=(
            expected - 90
        ),
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=32,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


def _observation(
    *,
    reservation_id,
    restaurant_id,
    actual=108,
):
    reservation_time = datetime(
        2026,
        9,
        4,
        19,
        0,
    )

    seated_at = (
        reservation_time
        + timedelta(minutes=5)
    )

    return TemporalTurnObservation(
        reservation_id=reservation_id,
        restaurant_id=restaurant_id,
        table_id=uuid4(),
        service_area_id=uuid4(),
        party_size=4,
        reservation_time=reservation_time,
        seated_at=seated_at,
        completed_at=(
            seated_at
            + timedelta(minutes=actual)
        ),
        planned_duration_minutes=90,
        actual_dining_minutes=actual,
        duration_delta_minutes=(
            actual - 90
        ),
    )


def test_records_prediction_truth_before_outcome():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    predicted_at = datetime(
        2026,
        9,
        4,
        18,
        30,
    )

    record = (
        TemporalPredictionTruthService.record(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            predicted_at=predicted_at,
            prediction=_prediction(
                expected=102,
            ),
        )
    )

    assert (
        record.reservation_id
        == reservation_id
    )

    assert (
        record.restaurant_id
        == restaurant_id
    )

    assert (
        record.predicted_at
        == predicted_at
    )

    assert (
        record.expected_duration_minutes
        == 102
    )

    assert (
        record.planned_duration_minutes
        == 90
    )

    assert record.adjustment_minutes == 12

    assert (
        record.source
        == ExpectedTurnSource.PARTY_SIZE
    )

    assert record.source_sample_count == 32

    assert (
        record.confidence
        == ExpectedTurnConfidence.HIGH
    )

    assert (
        record.used_learned_pattern
        is True
    )


def test_evaluates_positive_prediction_error():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    record = (
        TemporalPredictionTruthService.record(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            predicted_at=datetime(
                2026,
                9,
                4,
                18,
                30,
            ),
            prediction=_prediction(
                expected=100,
            ),
        )
    )

    outcome = (
        TemporalPredictionTruthService.evaluate(
            prediction=record,
            observation=_observation(
                reservation_id=reservation_id,
                restaurant_id=restaurant_id,
                actual=108,
            ),
        )
    )

    assert (
        outcome.predicted_duration_minutes
        == 100
    )

    assert (
        outcome.actual_duration_minutes
        == 108
    )

    assert (
        outcome.signed_error_minutes
        == 8
    )

    assert (
        outcome.absolute_error_minutes
        == 8
    )


def test_evaluates_negative_prediction_error():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    record = (
        TemporalPredictionTruthService.record(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            predicted_at=datetime(
                2026,
                9,
                4,
                18,
                30,
            ),
            prediction=_prediction(
                expected=100,
            ),
        )
    )

    outcome = (
        TemporalPredictionTruthService.evaluate(
            prediction=record,
            observation=_observation(
                reservation_id=reservation_id,
                restaurant_id=restaurant_id,
                actual=92,
            ),
        )
    )

    assert (
        outcome.signed_error_minutes
        == -8
    )

    assert (
        outcome.absolute_error_minutes
        == 8
    )


def test_exact_prediction_has_zero_error():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    record = (
        TemporalPredictionTruthService.record(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            predicted_at=datetime(
                2026,
                9,
                4,
                18,
                30,
            ),
            prediction=_prediction(
                expected=100,
            ),
        )
    )

    outcome = (
        TemporalPredictionTruthService.evaluate(
            prediction=record,
            observation=_observation(
                reservation_id=reservation_id,
                restaurant_id=restaurant_id,
                actual=100,
            ),
        )
    )

    assert (
        outcome.signed_error_minutes
        == 0
    )

    assert (
        outcome.absolute_error_minutes
        == 0
    )


def test_rejects_different_reservation():
    restaurant_id = uuid4()

    record = (
        TemporalPredictionTruthService.record(
            reservation_id=uuid4(),
            restaurant_id=restaurant_id,
            predicted_at=datetime(
                2026,
                9,
                4,
                18,
                30,
            ),
            prediction=_prediction(),
        )
    )

    with pytest.raises(
        ValueError,
        match="same reservation",
    ):
        TemporalPredictionTruthService.evaluate(
            prediction=record,
            observation=_observation(
                reservation_id=uuid4(),
                restaurant_id=restaurant_id,
            ),
        )


def test_rejects_different_restaurant():
    reservation_id = uuid4()

    record = (
        TemporalPredictionTruthService.record(
            reservation_id=reservation_id,
            restaurant_id=uuid4(),
            predicted_at=datetime(
                2026,
                9,
                4,
                18,
                30,
            ),
            prediction=_prediction(),
        )
    )

    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        TemporalPredictionTruthService.evaluate(
            prediction=record,
            observation=_observation(
                reservation_id=reservation_id,
                restaurant_id=uuid4(),
            ),
        )