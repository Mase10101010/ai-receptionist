from __future__ import annotations

from pydantic import BaseModel

from .prediction_truth import (
    TemporalTurnPredictionOutcome,
)


class TemporalAccuracyMetrics(BaseModel):
    sample_count: int

    mean_absolute_error_minutes: float | None
    mean_signed_error_minutes: float | None

    underprediction_count: int
    underprediction_rate: float | None

    overprediction_count: int
    overprediction_rate: float | None

    exact_count: int
    exact_rate: float | None

    within_5_minutes_count: int
    within_5_minutes_rate: float | None

    within_10_minutes_count: int
    within_10_minutes_rate: float | None


class TemporalCalibrationMetricsService:
    """
    Pure temporal accuracy metrics.

    Input:
    - typed TemporalTurnPredictionOutcome records

    Output:
    - aggregate accuracy metrics

    No DB access.
    No persistence.
    No calibration state classification.
    No confidence mutation.
    No Brain / optimizer / Autopilot integration.
    """

    @staticmethod
    def calculate(
        outcomes: list[TemporalTurnPredictionOutcome],
    ) -> TemporalAccuracyMetrics:
        sample_count = len(outcomes)

        if sample_count == 0:
            return TemporalAccuracyMetrics(
                sample_count=0,
                mean_absolute_error_minutes=None,
                mean_signed_error_minutes=None,
                underprediction_count=0,
                underprediction_rate=None,
                overprediction_count=0,
                overprediction_rate=None,
                exact_count=0,
                exact_rate=None,
                within_5_minutes_count=0,
                within_5_minutes_rate=None,
                within_10_minutes_count=0,
                within_10_minutes_rate=None,
            )

        total_absolute_error = sum(
            outcome.absolute_error_minutes
            for outcome in outcomes
        )

        total_signed_error = sum(
            outcome.signed_error_minutes
            for outcome in outcomes
        )

        underprediction_count = sum(
            1
            for outcome in outcomes
            if outcome.signed_error_minutes > 0
        )

        overprediction_count = sum(
            1
            for outcome in outcomes
            if outcome.signed_error_minutes < 0
        )

        exact_count = sum(
            1
            for outcome in outcomes
            if outcome.signed_error_minutes == 0
        )

        within_5_minutes_count = sum(
            1
            for outcome in outcomes
            if outcome.absolute_error_minutes <= 5
        )

        within_10_minutes_count = sum(
            1
            for outcome in outcomes
            if outcome.absolute_error_minutes <= 10
        )

        return TemporalAccuracyMetrics(
            sample_count=sample_count,
            mean_absolute_error_minutes=(
                total_absolute_error
                / sample_count
            ),
            mean_signed_error_minutes=(
                total_signed_error
                / sample_count
            ),
            underprediction_count=(
                underprediction_count
            ),
            underprediction_rate=(
                underprediction_count
                / sample_count
            ),
            overprediction_count=(
                overprediction_count
            ),
            overprediction_rate=(
                overprediction_count
                / sample_count
            ),
            exact_count=exact_count,
            exact_rate=(
                exact_count
                / sample_count
            ),
            within_5_minutes_count=(
                within_5_minutes_count
            ),
            within_5_minutes_rate=(
                within_5_minutes_count
                / sample_count
            ),
            within_10_minutes_count=(
                within_10_minutes_count
            ),
            within_10_minutes_rate=(
                within_10_minutes_count
                / sample_count
            ),
        )