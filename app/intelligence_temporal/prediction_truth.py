from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from .observations import TemporalTurnObservation
from .prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnPrediction,
    ExpectedTurnSource,
)


class TemporalTurnPredictionRecord(BaseModel):
    """
    Immutable truth about what Alias predicted before
    the real turn outcome was known.
    """

    reservation_id: UUID
    restaurant_id: UUID

    predicted_at: datetime

    expected_duration_minutes: int
    planned_duration_minutes: int
    adjustment_minutes: int

    source: ExpectedTurnSource
    source_sample_count: int | None = None

    confidence: ExpectedTurnConfidence

    used_learned_pattern: bool


class TemporalTurnPredictionOutcome(BaseModel):
    """
    Joins one historical prediction with its observed
    completed turn.

    Error convention:

        signed_error_minutes
        = actual - predicted

    Positive:
        turn lasted longer than Alias expected.

    Negative:
        turn finished earlier than Alias expected.
    """

    reservation_id: UUID
    restaurant_id: UUID

    predicted_at: datetime
    completed_at: datetime

    predicted_duration_minutes: int
    actual_duration_minutes: int

    signed_error_minutes: int
    absolute_error_minutes: int

    source: ExpectedTurnSource
    source_sample_count: int | None = None

    confidence: ExpectedTurnConfidence
    used_learned_pattern: bool


class TemporalPredictionTruthService:
    """
    Pure prediction/outcome truth service.

    No DB access.
    No calibration.
    No aggregation.
    No persistence.
    """

    @staticmethod
    def record(
        *,
        reservation_id: UUID,
        restaurant_id: UUID,
        predicted_at: datetime,
        prediction: ExpectedTurnPrediction,
    ) -> TemporalTurnPredictionRecord:
        return TemporalTurnPredictionRecord(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            predicted_at=predicted_at,
            expected_duration_minutes=(
                prediction.expected_duration_minutes
            ),
            planned_duration_minutes=(
                prediction.planned_duration_minutes
            ),
            adjustment_minutes=(
                prediction.adjustment_minutes
            ),
            source=prediction.source,
            source_sample_count=(
                prediction.source_sample_count
            ),
            confidence=prediction.confidence,
            used_learned_pattern=(
                prediction.used_learned_pattern
            ),
        )

    @staticmethod
    def evaluate(
        *,
        prediction: TemporalTurnPredictionRecord,
        observation: TemporalTurnObservation,
    ) -> TemporalTurnPredictionOutcome:
        if (
            prediction.reservation_id
            != observation.reservation_id
        ):
            raise ValueError(
                "Prediction and observation must belong "
                "to the same reservation."
            )

        if (
            prediction.restaurant_id
            != observation.restaurant_id
        ):
            raise ValueError(
                "Prediction and observation must belong "
                "to the same restaurant."
            )

        signed_error = (
            observation.actual_dining_minutes
            - prediction.expected_duration_minutes
        )

        return TemporalTurnPredictionOutcome(
            reservation_id=prediction.reservation_id,
            restaurant_id=prediction.restaurant_id,
            predicted_at=prediction.predicted_at,
            completed_at=observation.completed_at,
            predicted_duration_minutes=(
                prediction.expected_duration_minutes
            ),
            actual_duration_minutes=(
                observation.actual_dining_minutes
            ),
            signed_error_minutes=signed_error,
            absolute_error_minutes=abs(
                signed_error
            ),
            source=prediction.source,
            source_sample_count=(
                prediction.source_sample_count
            ),
            confidence=prediction.confidence,
            used_learned_pattern=(
                prediction.used_learned_pattern
            ),
        )