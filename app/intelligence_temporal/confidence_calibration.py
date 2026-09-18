from __future__ import annotations

from pydantic import BaseModel

from .calibration_metrics import (
    TemporalAccuracyMetrics,
    TemporalCalibrationMetricsService,
)
from .prediction import (
    ExpectedTurnConfidence,
)
from .prediction_truth import (
    TemporalTurnPredictionOutcome,
)


class TemporalConfidenceCalibration(BaseModel):
    confidence: ExpectedTurnConfidence
    metrics: TemporalAccuracyMetrics


class TemporalConfidenceCalibrationSnapshot(BaseModel):
    low: TemporalConfidenceCalibration
    medium: TemporalConfidenceCalibration
    high: TemporalConfidenceCalibration


class TemporalConfidenceCalibrationService:
    """
    Pure confidence calibration breakdown.

    Responsibilities:
    - group temporal prediction outcomes by declared confidence
    - reuse TemporalCalibrationMetricsService
    - return typed accuracy metrics for LOW / MEDIUM / HIGH

    No DB access.
    No persistence.
    No calibration-state classification.
    No Brain / optimizer / Autopilot integration.
    """

    @staticmethod
    def calculate(
        outcomes: list[TemporalTurnPredictionOutcome],
    ) -> TemporalConfidenceCalibrationSnapshot:
        grouped: dict[
            ExpectedTurnConfidence,
            list[TemporalTurnPredictionOutcome],
        ] = {
            ExpectedTurnConfidence.LOW: [],
            ExpectedTurnConfidence.MEDIUM: [],
            ExpectedTurnConfidence.HIGH: [],
        }

        for outcome in outcomes:
            grouped[outcome.confidence].append(
                outcome
            )

        return TemporalConfidenceCalibrationSnapshot(
            low=TemporalConfidenceCalibration(
                confidence=ExpectedTurnConfidence.LOW,
                metrics=(
                    TemporalCalibrationMetricsService
                    .calculate(
                        grouped[
                            ExpectedTurnConfidence.LOW
                        ]
                    )
                ),
            ),
            medium=TemporalConfidenceCalibration(
                confidence=ExpectedTurnConfidence.MEDIUM,
                metrics=(
                    TemporalCalibrationMetricsService
                    .calculate(
                        grouped[
                            ExpectedTurnConfidence.MEDIUM
                        ]
                    )
                ),
            ),
            high=TemporalConfidenceCalibration(
                confidence=ExpectedTurnConfidence.HIGH,
                metrics=(
                    TemporalCalibrationMetricsService
                    .calculate(
                        grouped[
                            ExpectedTurnConfidence.HIGH
                        ]
                    )
                ),
            ),
        )