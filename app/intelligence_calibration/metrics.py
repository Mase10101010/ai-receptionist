from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_calibration.repository import (
    IntelligenceCalibrationRepository,
)
from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
    CalibrationState,
)


class IntelligenceCalibrationMetricsService:
    def __init__(
        self,
        *,
        repository: IntelligenceCalibrationRepository,
    ) -> None:
        self.repository = repository

    async def calculate(
        self,
        *,
        restaurant_id: uuid.UUID,
    ) -> CalibrationMetrics:
        events = (
            await self.repository
            .list_evaluated_predictions(
                restaurant_id=restaurant_id,
            )
        )

        count = len(events)

        if count == 0:
            return CalibrationMetrics(
                restaurant_id=restaurant_id,
                predictions_evaluated=0,
                correct_predictions=0,
                prediction_accuracy=0.0,
                average_absolute_error=0.0,
                brier_score=0.0,
                average_predicted_probability=0.0,
                actual_acceptance_rate=0.0,
                calibration_gap=0.0,
                state=(
                    CalibrationState
                    .INSUFFICIENT_DATA
                ),
                generated_at=datetime.now(
                    timezone.utc,
                ),
            )

        probabilities: list[float] = []
        actual_values: list[float] = []
        absolute_errors: list[float] = []
        squared_errors: list[float] = []

        correct_predictions = 0

        for event in events:
            payload = event.payload

            probability = float(
                payload[
                    "predicted_acceptance_probability"
                ]
            )

            actual_value = float(
                payload[
                    "calibration_actual_value"
                ]
            )

            absolute_error = float(
                payload[
                    "calibration_absolute_error"
                ]
            )

            squared_error = float(
                payload[
                    "calibration_squared_error"
                ]
            )

            probabilities.append(
                probability
            )
            actual_values.append(
                actual_value
            )
            absolute_errors.append(
                absolute_error
            )
            squared_errors.append(
                squared_error
            )

            if payload.get(
                "prediction_correct"
            ) is True:
                correct_predictions += 1

        average_probability = (
            sum(probabilities) / count
        )

        actual_acceptance_rate = (
            sum(actual_values) / count
        )

        calibration_gap = (
            average_probability
            - actual_acceptance_rate
        )

        prediction_accuracy = (
            correct_predictions / count
        )

        average_absolute_error = (
            sum(absolute_errors) / count
        )

        brier_score = (
            sum(squared_errors) / count
        )

        state = self._state(
            predictions_evaluated=count,
            calibration_gap=(
                calibration_gap
            ),
        )

        return CalibrationMetrics(
            restaurant_id=restaurant_id,
            predictions_evaluated=count,
            correct_predictions=(
                correct_predictions
            ),
            prediction_accuracy=round(
                prediction_accuracy,
                4,
            ),
            average_absolute_error=round(
                average_absolute_error,
                4,
            ),
            brier_score=round(
                brier_score,
                6,
            ),
            average_predicted_probability=round(
                average_probability,
                4,
            ),
            actual_acceptance_rate=round(
                actual_acceptance_rate,
                4,
            ),
            calibration_gap=round(
                calibration_gap,
                4,
            ),
            state=state,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    @staticmethod
    def _state(
        *,
        predictions_evaluated: int,
        calibration_gap: float,
    ) -> CalibrationState:
        if predictions_evaluated < 10:
            return (
                CalibrationState
                .INSUFFICIENT_DATA
            )

        if calibration_gap > 0.10:
            return (
                CalibrationState
                .OVERCONFIDENT
            )

        if calibration_gap < -0.10:
            return (
                CalibrationState
                .UNDERCONFIDENT
            )

        return (
            CalibrationState
            .WELL_CALIBRATED
        )