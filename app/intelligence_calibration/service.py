from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_calibration.schemas import (
    PredictionEvaluation,
    PredictionOutcome,
)


class IntelligenceCalibrationService:
    def evaluate_prediction(
        self,
        *,
        restaurant_id: uuid.UUID,
        suggestion_id: uuid.UUID,
        predicted_probability: float,
        actual_outcome: PredictionOutcome,
    ) -> PredictionEvaluation:
        probability = max(
            0.0,
            min(
                1.0,
                predicted_probability,
            ),
        )

        actual_value = (
            1.0
            if actual_outcome
            == PredictionOutcome.ACCEPTED
            else 0.0
        )

        absolute_error = abs(
            actual_value - probability
        )

        squared_error = (
            actual_value - probability
        ) ** 2

        if probability >= 0.5:
            predicted_acceptance = True
        else:
            predicted_acceptance = False

        actual_acceptance = (
            actual_outcome
            == PredictionOutcome.ACCEPTED
        )

        prediction_correct = (
            predicted_acceptance
            == actual_acceptance
        )

        return PredictionEvaluation(
            restaurant_id=restaurant_id,
            suggestion_id=suggestion_id,
            predicted_probability=round(
                probability,
                4,
            ),
            actual_outcome=actual_outcome,
            actual_value=actual_value,
            absolute_error=round(
                absolute_error,
                4,
            ),
            squared_error=round(
                squared_error,
                6,
            ),
            prediction_correct=(
                prediction_correct
            ),
            generated_at=datetime.now(
                timezone.utc,
            ),
        )