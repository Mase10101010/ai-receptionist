from __future__ import annotations

from pydantic import BaseModel, Field

from .calibration_state import (
    TemporalCalibrationState,
)
from .prediction import (
    ExpectedTurnConfidence,
)


class TemporalAutopilotSafetyContext(BaseModel):
    """
    Temporal evidence used only to veto an already-authorized
    automatic action.

    This context is not an execution authority.
    """

    calibration_state: TemporalCalibrationState | None

    expected_turn_confidence: (
        ExpectedTurnConfidence | None
    )

    marginal_capacity_loss_ratio: float | None = Field(
        default=None,
        ge=0.0,
    )

    lost_future_available_slots: int | None = Field(
        default=None,
        ge=0,
    )


class TemporalAutopilotGuardResult(BaseModel):
    """
    Result of the Temporal Autopilot safety guard.

    allowed=True means only:
        Temporal Intelligence does not veto the action.

    It never means:
        the action is automatically authorized.
    """

    allowed: bool

    reasons: tuple[str, ...] = ()


class TemporalAutopilotGuardService:
    """
    Conservative Temporal Autopilot safety policy V1.

    Hard authority invariant:

        existing execution authority
            AND
        temporal safety guard

    Temporal Intelligence may remove autonomy.
    Temporal Intelligence may never grant autonomy.

    V1 requires:
    - WELL_CALIBRATED temporal predictions
    - HIGH expected-turn confidence
    - zero known lost future available slots
    - zero known marginal future-capacity loss

    Missing evidence fails closed.

    No:
    - DB
    - persistence
    - execution
    - ranking
    - score mutation
    - Brain
    - Autopilot opt-in evaluation
    - execution eligibility evaluation
    - ML
    """

    @classmethod
    def evaluate(
        cls,
        *,
        context: TemporalAutopilotSafetyContext | None,
    ) -> TemporalAutopilotGuardResult:
        if context is None:
            return TemporalAutopilotGuardResult(
                allowed=False,
                reasons=(
                    "Temporal safety context is missing.",
                ),
            )

        reasons: list[str] = []

        if (
            context.calibration_state
            != TemporalCalibrationState.WELL_CALIBRATED
        ):
            reasons.append(
                "Temporal calibration is not well calibrated."
            )

        if (
            context.expected_turn_confidence
            != ExpectedTurnConfidence.HIGH
        ):
            reasons.append(
                "Expected turn confidence is not high."
            )

        if context.lost_future_available_slots is None:
            reasons.append(
                "Future capacity loss is unknown."
            )
        elif context.lost_future_available_slots > 0:
            reasons.append(
                "The action would remove future available slots."
            )

        if context.marginal_capacity_loss_ratio is None:
            reasons.append(
                "Marginal future capacity loss is unknown."
            )
        elif context.marginal_capacity_loss_ratio > 0.0:
            reasons.append(
                "The action has known marginal future capacity loss."
            )

        return TemporalAutopilotGuardResult(
            allowed=not reasons,
            reasons=tuple(reasons),
        )