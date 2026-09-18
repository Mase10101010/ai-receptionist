from __future__ import annotations

import pytest

from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationAssessment,
    TemporalCalibrationState,
)
from app.intelligence_temporal.optimization_duration import (
    TemporalOptimizationDurationPolicy,
    TemporalOptimizationDurationSource,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnPrediction,
    ExpectedTurnSource,
)


def _prediction(
    *,
    planned: int = 90,
    expected: int = 105,
    confidence: ExpectedTurnConfidence = (
        ExpectedTurnConfidence.HIGH
    ),
    learned: bool = True,
) -> ExpectedTurnPrediction:
    return ExpectedTurnPrediction(
        expected_duration_minutes=expected,
        planned_duration_minutes=planned,
        adjustment_minutes=(
            expected - planned
        ),
        source=(
            ExpectedTurnSource.PARTY_SIZE
            if learned
            else ExpectedTurnSource.PLANNED_FALLBACK
        ),
        source_sample_count=(
            40
            if learned
            else None
        ),
        confidence=confidence,
        used_learned_pattern=learned,
    )


def _calibration(
    state: TemporalCalibrationState,
) -> TemporalCalibrationAssessment:
    return TemporalCalibrationAssessment(
        state=state,
        sample_count=30,
        mean_absolute_error_minutes=8.0,
        mean_signed_error_minutes=1.0,
    )


def test_high_confidence_well_calibrated_uses_expected():
    result = (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=_prediction(
                planned=90,
                expected=105,
            ),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert result.duration_minutes == 105

    assert (
        result.source
        == TemporalOptimizationDurationSource.EXPECTED
    )

    assert result.used_expected_duration is True


def test_low_confidence_uses_planned():
    result = (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=_prediction(
                confidence=(
                    ExpectedTurnConfidence.LOW
                ),
            ),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert result.duration_minutes == 90
    assert result.used_expected_duration is False


def test_medium_confidence_uses_planned():
    result = (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=_prediction(
                confidence=(
                    ExpectedTurnConfidence.MEDIUM
                ),
            ),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert result.duration_minutes == 90
    assert result.used_expected_duration is False


@pytest.mark.parametrize(
    "state",
    [
        TemporalCalibrationState.INSUFFICIENT_DATA,
        TemporalCalibrationState.UNDERPREDICTING,
        TemporalCalibrationState.OVERPREDICTING,
        TemporalCalibrationState.UNRELIABLE,
    ],
)
def test_non_well_calibrated_states_use_planned(
    state,
):
    result = (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=_prediction(),
            calibration=_calibration(
                state,
            ),
        )
    )

    assert result.duration_minutes == 90
    assert result.used_expected_duration is False


def test_planned_fallback_never_uses_expected():
    result = (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=_prediction(
                planned=90,
                expected=90,
                confidence=(
                    ExpectedTurnConfidence.LOW
                ),
                learned=False,
            ),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert result.duration_minutes == 90

    assert (
        result.source
        == TemporalOptimizationDurationSource.PLANNED
    )

    assert result.used_expected_duration is False


def test_does_not_change_prediction_truth():
    prediction = _prediction(
        planned=90,
        expected=110,
    )

    (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=prediction,
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert prediction.planned_duration_minutes == 90
    assert prediction.expected_duration_minutes == 110


def test_shorter_expected_duration_can_be_used():
    result = (
        TemporalOptimizationDurationPolicy
        .decide(
            prediction=_prediction(
                planned=90,
                expected=75,
            ),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert result.duration_minutes == 75
    assert result.used_expected_duration is True