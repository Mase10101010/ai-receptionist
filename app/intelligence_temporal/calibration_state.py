from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .calibration_metrics import (
    TemporalAccuracyMetrics,
)


class TemporalCalibrationState(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    WELL_CALIBRATED = "well_calibrated"
    UNDERPREDICTING = "underpredicting"
    OVERPREDICTING = "overpredicting"
    UNRELIABLE = "unreliable"


class TemporalCalibrationAssessment(BaseModel):
    state: TemporalCalibrationState
    sample_count: int
    mean_absolute_error_minutes: float | None
    mean_signed_error_minutes: float | None


class TemporalCalibrationStateService:
    """
    Deterministic Temporal Calibration V1 classifier.

    Semantics:

    INSUFFICIENT_DATA
        Not enough completed prediction outcomes.

    UNRELIABLE
        Prediction errors are too large overall, regardless
        of whether positive and negative errors cancel out.

    UNDERPREDICTING
        Alias systematically predicts turns shorter than
        reality.

    OVERPREDICTING
        Alias systematically predicts turns longer than
        reality.

    WELL_CALIBRATED
        Mature evidence, acceptable absolute error and no
        material directional bias.

    No DB access.
    No persistence.
    No confidence mutation.
    No Brain / optimizer / Autopilot integration.
    """

    MINIMUM_SAMPLE_COUNT = 15

    MAX_ACCEPTABLE_MAE_MINUTES = 15.0

    MATERIAL_BIAS_MINUTES = 5.0

    @classmethod
    def assess(
        cls,
        metrics: TemporalAccuracyMetrics,
    ) -> TemporalCalibrationAssessment:
        if (
            metrics.sample_count
            < cls.MINIMUM_SAMPLE_COUNT
        ):
            state = (
                TemporalCalibrationState
                .INSUFFICIENT_DATA
            )

        elif (
            metrics.mean_absolute_error_minutes
            is None
            or metrics.mean_signed_error_minutes
            is None
        ):
            state = (
                TemporalCalibrationState
                .INSUFFICIENT_DATA
            )

        elif (
            metrics.mean_absolute_error_minutes
            > cls.MAX_ACCEPTABLE_MAE_MINUTES
        ):
            state = (
                TemporalCalibrationState
                .UNRELIABLE
            )

        elif (
            metrics.mean_signed_error_minutes
            >= cls.MATERIAL_BIAS_MINUTES
        ):
            state = (
                TemporalCalibrationState
                .UNDERPREDICTING
            )

        elif (
            metrics.mean_signed_error_minutes
            <= -cls.MATERIAL_BIAS_MINUTES
        ):
            state = (
                TemporalCalibrationState
                .OVERPREDICTING
            )

        else:
            state = (
                TemporalCalibrationState
                .WELL_CALIBRATED
            )

        return TemporalCalibrationAssessment(
            state=state,
            sample_count=metrics.sample_count,
            mean_absolute_error_minutes=(
                metrics.mean_absolute_error_minutes
            ),
            mean_signed_error_minutes=(
                metrics.mean_signed_error_minutes
            ),
        )