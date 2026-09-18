from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel

from .prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnPrediction,
    ExpectedTurnSource,
)


class LiveTurnState(str, Enum):
    IN_PROGRESS = "in_progress"
    EXPECTED_RELEASE_REACHED = (
        "expected_release_reached"
    )
    OVERRUN = "overrun"


class LiveTurnPrediction(BaseModel):
    seated_at: datetime
    evaluated_at: datetime

    expected_duration_minutes: int
    expected_release_at: datetime

    elapsed_minutes: int
    remaining_minutes: int
    overrun_minutes: int

    state: LiveTurnState

    source: ExpectedTurnSource
    source_sample_count: int | None

    confidence: ExpectedTurnConfidence
    used_learned_pattern: bool


class LiveTurnPredictionService:
    """
    Pure live-turn timing calculation.

    Takes:
    - actual seated_at truth
    - an ExpectedTurnPrediction
    - current evaluation time

    Produces:
    - expected release timestamp
    - elapsed dining time
    - expected remaining time
    - deterministic overrun time
    - current temporal state

    This does NOT yet:
    - calculate probability intervals
    - calculate probabilistic overrun risk
    - persist events
    - update Brain
    - update optimizer
    - trigger Autopilot
    """

    @staticmethod
    def calculate(
        *,
        seated_at: datetime,
        prediction: ExpectedTurnPrediction,
        evaluated_at: datetime,
    ) -> LiveTurnPrediction:
        expected_release_at = (
            seated_at
            + timedelta(
                minutes=(
                    prediction
                    .expected_duration_minutes
                )
            )
        )

        elapsed_seconds = (
            evaluated_at - seated_at
        ).total_seconds()

        elapsed_minutes = max(
            0,
            int(elapsed_seconds // 60),
        )

        remaining_seconds = (
            expected_release_at
            - evaluated_at
        ).total_seconds()

        remaining_minutes = max(
            0,
            int(
                (
                    remaining_seconds
                    + 59
                )
                // 60
            ),
        )

        overrun_seconds = (
            evaluated_at
            - expected_release_at
        ).total_seconds()

        overrun_minutes = max(
            0,
            int(overrun_seconds // 60),
        )

        if evaluated_at < expected_release_at:
            state = LiveTurnState.IN_PROGRESS

        elif evaluated_at == expected_release_at:
            state = (
                LiveTurnState
                .EXPECTED_RELEASE_REACHED
            )

        else:
            state = LiveTurnState.OVERRUN

        return LiveTurnPrediction(
            seated_at=seated_at,
            evaluated_at=evaluated_at,
            expected_duration_minutes=(
                prediction
                .expected_duration_minutes
            ),
            expected_release_at=(
                expected_release_at
            ),
            elapsed_minutes=elapsed_minutes,
            remaining_minutes=remaining_minutes,
            overrun_minutes=overrun_minutes,
            state=state,
            source=prediction.source,
            source_sample_count=(
                prediction.source_sample_count
            ),
            confidence=prediction.confidence,
            used_learned_pattern=(
                prediction.used_learned_pattern
            ),
        )