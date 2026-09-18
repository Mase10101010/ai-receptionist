from __future__ import annotations

from pydantic import BaseModel

from .calibration_metrics import (
    TemporalAccuracyMetrics,
    TemporalCalibrationMetricsService,
)
from .prediction import ExpectedTurnSource
from .prediction_truth import (
    TemporalTurnPredictionOutcome,
)


class TemporalSourceCalibration(BaseModel):
    source: ExpectedTurnSource
    metrics: TemporalAccuracyMetrics


class TemporalSourceCalibrationSnapshot(BaseModel):
    sources: list[TemporalSourceCalibration]

    def for_source(
        self,
        source: ExpectedTurnSource,
    ) -> TemporalSourceCalibration:
        for item in self.sources:
            if item.source == source:
                return item

        raise KeyError(source)


class TemporalSourceCalibrationService:
    """
    Pure prediction-source calibration breakdown.

    Responsibilities:
    - group outcomes by ExpectedTurnSource
    - reuse canonical temporal accuracy metrics
    - preserve all known sources, including empty buckets

    No DB access.
    No persistence.
    No calibration-state classification.
    No Brain / optimizer / Autopilot integration.
    """

    @staticmethod
    def calculate(
        outcomes: list[TemporalTurnPredictionOutcome],
    ) -> TemporalSourceCalibrationSnapshot:
        grouped: dict[
            ExpectedTurnSource,
            list[TemporalTurnPredictionOutcome],
        ] = {
            source: []
            for source in ExpectedTurnSource
        }

        for outcome in outcomes:
            grouped[outcome.source].append(outcome)

        return TemporalSourceCalibrationSnapshot(
            sources=[
                TemporalSourceCalibration(
                    source=source,
                    metrics=(
                        TemporalCalibrationMetricsService
                        .calculate(grouped[source])
                    ),
                )
                for source in ExpectedTurnSource
            ]
        )