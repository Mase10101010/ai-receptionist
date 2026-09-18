from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from .calibration_state import (
    TemporalCalibrationAssessment,
    TemporalCalibrationState,
)
from .error_distribution import (
    TemporalErrorDistribution,
)
from .live_turn import LiveTurnPrediction


class TemporalReleaseWindow(BaseModel):
    expected_release_at: datetime

    window_start_at: datetime | None
    window_end_at: datetime | None

    available: bool
    sample_count: int

    calibration_state: TemporalCalibrationState


class TemporalReleaseWindowService:
    """
    Builds a conservative empirical release window.

    The window is derived from historical signed prediction errors:

        actual_duration - predicted_duration

    Therefore:
        expected_release + P10 error -> early bound
        expected_release + P90 error -> late bound

    The window is exposed only when temporal calibration is mature
    and WELL_CALIBRATED.

    This is an empirical historical window, not a formal probabilistic
    confidence interval.

    No DB access.
    No persistence.
    No Brain / optimizer / Autopilot integration.
    """

    MINIMUM_SAMPLE_COUNT = 15

    @classmethod
    def calculate(
        cls,
        *,
        live_turn: LiveTurnPrediction,
        distribution: TemporalErrorDistribution,
        assessment: TemporalCalibrationAssessment,
    ) -> TemporalReleaseWindow:
        if (
            distribution.sample_count
            < cls.MINIMUM_SAMPLE_COUNT
        ):
            return cls._unavailable(
                live_turn=live_turn,
                distribution=distribution,
                assessment=assessment,
            )

        if (
            assessment.state
            != TemporalCalibrationState.WELL_CALIBRATED
        ):
            return cls._unavailable(
                live_turn=live_turn,
                distribution=distribution,
                assessment=assessment,
            )

        lower_error = (
            distribution.p10_signed_error_minutes
        )

        upper_error = (
            distribution.p90_signed_error_minutes
        )

        if (
            lower_error is None
            or upper_error is None
        ):
            return cls._unavailable(
                live_turn=live_turn,
                distribution=distribution,
                assessment=assessment,
            )

        window_start_at = (
            live_turn.expected_release_at
            + timedelta(minutes=lower_error)
        )

        window_end_at = (
            live_turn.expected_release_at
            + timedelta(minutes=upper_error)
        )

        if window_start_at > window_end_at:
            return cls._unavailable(
                live_turn=live_turn,
                distribution=distribution,
                assessment=assessment,
            )

        return TemporalReleaseWindow(
            expected_release_at=(
                live_turn.expected_release_at
            ),
            window_start_at=window_start_at,
            window_end_at=window_end_at,
            available=True,
            sample_count=distribution.sample_count,
            calibration_state=assessment.state,
        )

    @staticmethod
    def _unavailable(
        *,
        live_turn: LiveTurnPrediction,
        distribution: TemporalErrorDistribution,
        assessment: TemporalCalibrationAssessment,
    ) -> TemporalReleaseWindow:
        return TemporalReleaseWindow(
            expected_release_at=(
                live_turn.expected_release_at
            ),
            window_start_at=None,
            window_end_at=None,
            available=False,
            sample_count=distribution.sample_count,
            calibration_state=assessment.state,
        )