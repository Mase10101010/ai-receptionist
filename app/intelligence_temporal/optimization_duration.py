from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .calibration_state import (
    TemporalCalibrationAssessment,
    TemporalCalibrationState,
)
from .prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnPrediction,
)


class TemporalOptimizationDurationSource(
    str,
    Enum,
):
    PLANNED = "planned"
    EXPECTED = "expected"


class TemporalOptimizationDurationDecision(
    BaseModel
):
    duration_minutes: int

    planned_duration_minutes: int
    expected_duration_minutes: int

    source: TemporalOptimizationDurationSource

    prediction_confidence: (
        ExpectedTurnConfidence
    )

    calibration_state: TemporalCalibrationState

    used_expected_duration: bool


class TemporalOptimizationDurationPolicy:
    """
    Authority for choosing which duration temporal
    optimization may use.

    This does NOT change the reservation's planned
    duration.

    It only decides which occupancy duration may be
    used inside temporal counterfactual evaluation.

    Invariants:
    - pure
    - no DB
    - no persistence
    - no optimizer calls
    - no Brain
    - no Autopilot
    - no ML
    - uncertain truth -> planned duration
    """

    @staticmethod
    def decide(
        *,
        prediction: ExpectedTurnPrediction,
        calibration: TemporalCalibrationAssessment,
    ) -> TemporalOptimizationDurationDecision:
        trusted = (
            prediction.used_learned_pattern
            and prediction.confidence
            == ExpectedTurnConfidence.HIGH
            and calibration.state
            == TemporalCalibrationState.WELL_CALIBRATED
        )

        duration = (
            prediction.expected_duration_minutes
            if trusted
            else prediction.planned_duration_minutes
        )

        return TemporalOptimizationDurationDecision(
            duration_minutes=duration,
            planned_duration_minutes=(
                prediction.planned_duration_minutes
            ),
            expected_duration_minutes=(
                prediction.expected_duration_minutes
            ),
            source=(
                TemporalOptimizationDurationSource.EXPECTED
                if trusted
                else TemporalOptimizationDurationSource.PLANNED
            ),
            prediction_confidence=(
                prediction.confidence
            ),
            calibration_state=(
                calibration.state
            ),
            used_expected_duration=trusted,
        )