from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PredictionOutcome(str, Enum):
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class PredictionEvaluation(BaseModel):
    restaurant_id: uuid.UUID
    suggestion_id: uuid.UUID

    predicted_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    actual_outcome: PredictionOutcome

    actual_value: float = Field(
        ge=0.0,
        le=1.0,
    )

    absolute_error: float = Field(
        ge=0.0,
        le=1.0,
    )

    squared_error: float = Field(
        ge=0.0,
        le=1.0,
    )

    prediction_correct: bool

    generated_at: datetime

class CalibrationState(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    OVERCONFIDENT = "overconfident"
    WELL_CALIBRATED = "well_calibrated"
    UNDERCONFIDENT = "underconfident"


class CalibrationMetrics(BaseModel):
    restaurant_id: uuid.UUID

    predictions_evaluated: int

    correct_predictions: int
    prediction_accuracy: float

    average_absolute_error: float
    brier_score: float

    average_predicted_probability: float
    actual_acceptance_rate: float
    calibration_gap: float

    state: CalibrationState

    generated_at: datetime