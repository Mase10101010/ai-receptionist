from __future__ import annotations

from datetime import datetime, timezone

from app.intelligence_temporal.live_turn import (
    LiveTurnPredictionService,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnPrediction,
    ExpectedTurnSource,
)


def _prediction(
    *,
    expected_duration_minutes: int = 100,
) -> ExpectedTurnPrediction:
    return ExpectedTurnPrediction(
        expected_duration_minutes=(
            expected_duration_minutes
        ),
        planned_duration_minutes=90,
        adjustment_minutes=(
            expected_duration_minutes - 90
        ),
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        used_learned_pattern=True,
        confidence=ExpectedTurnConfidence.HIGH,
    )


def test_calculates_expected_release_from_actual_seated_time():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    evaluated_at = datetime(
        2026,
        9,
        6,
        19,
        30,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=evaluated_at,
    )

    assert live.expected_release_at == datetime(
        2026,
        9,
        6,
        20,
        40,
        tzinfo=timezone.utc,
    )


def test_calculates_elapsed_and_remaining_minutes():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    evaluated_at = datetime(
        2026,
        9,
        6,
        19,
        35,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=evaluated_at,
    )

    assert live.elapsed_minutes == 35
    assert live.remaining_minutes == 65


def test_remaining_time_never_becomes_negative():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    evaluated_at = datetime(
        2026,
        9,
        6,
        21,
        0,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=evaluated_at,
    )

    assert live.elapsed_minutes == 120
    assert live.remaining_minutes == 0


def test_evaluation_before_seating_does_not_create_negative_elapsed_time():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    evaluated_at = datetime(
        2026,
        9,
        6,
        18,
        55,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(),
        evaluated_at=evaluated_at,
    )

    assert live.elapsed_minutes == 0


def test_preserves_prediction_provenance():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=105,
        ),
        evaluated_at=seated_at,
    )

    assert live.expected_duration_minutes == 105

    assert (
        live.source
        == ExpectedTurnSource.PARTY_SIZE
    )

    assert live.source_sample_count == 30

    assert (
        live.confidence
        == ExpectedTurnConfidence.HIGH
    )

    assert live.used_learned_pattern is True

from app.intelligence_temporal.live_turn import (
    LiveTurnPredictionService,
    LiveTurnState,
)


def test_turn_is_in_progress_before_expected_release():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert live.state == LiveTurnState.IN_PROGRESS
    assert live.remaining_minutes == 10
    assert live.overrun_minutes == 0


def test_turn_reaches_expected_release_boundary():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            40,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        live.state
        == LiveTurnState.EXPECTED_RELEASE_REACHED
    )

    assert live.remaining_minutes == 0
    assert live.overrun_minutes == 0


def test_turn_becomes_overrun_after_expected_release():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=datetime(
            2026,
            9,
            6,
            20,
            52,
            tzinfo=timezone.utc,
        ),
    )

    assert live.state == LiveTurnState.OVERRUN
    assert live.remaining_minutes == 0
    assert live.overrun_minutes == 12


def test_overrun_never_becomes_negative():
    seated_at = datetime(
        2026,
        9,
        6,
        19,
        0,
        tzinfo=timezone.utc,
    )

    live = LiveTurnPredictionService.calculate(
        seated_at=seated_at,
        prediction=_prediction(
            expected_duration_minutes=100,
        ),
        evaluated_at=datetime(
            2026,
            9,
            6,
            19,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert live.overrun_minutes == 0