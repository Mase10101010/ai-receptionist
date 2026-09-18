from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from .autopilot_guard import (
    TemporalAutopilotGuardService,
    TemporalAutopilotSafetyContext,
)
from .calibration_state import (
    TemporalCalibrationState,
)
from .prediction import (
    ExpectedTurnConfidence,
)


class TemporalAffectedReservationEvidence(BaseModel):
    """
    Expected-turn evidence for one reservation affected by
    a reoptimization plan.
    """

    reservation_id: UUID
    expected_turn_confidence: ExpectedTurnConfidence


class TemporalReoptimizationSafetyInput(BaseModel):
    """
    Complete temporal evidence required to assess one exact
    reoptimization plan.

    Evidence calculation happens elsewhere.
    """

    calibration_state: TemporalCalibrationState | None

    affected_reservations: tuple[
        TemporalAffectedReservationEvidence,
        ...
    ] = ()

    marginal_capacity_loss_ratio: float | None = Field(
        default=None,
        ge=0.0,
    )

    lost_future_available_slots: int | None = Field(
        default=None,
        ge=0,
    )


class TemporalReoptimizationSafetyResult(BaseModel):
    context: TemporalAutopilotSafetyContext | None

    complete: bool

    reasons: tuple[str, ...] = ()


class TemporalReoptimizationSafetyService:
    """
    Conservative plan-level Temporal Autopilot evidence
    composition.

    V1 invariants:
    - every reservation affected by the plan must have
      HIGH expected-turn confidence
    - calibration must be available
    - future-capacity impact must be available
    - incomplete evidence fails closed
    - no DB
    - no persistence
    - no prediction
    - no calibration calculation
    - no future-capacity calculation
    - no ranking
    - no execution
    - no Autopilot authority
    - no Brain
    - no ML
    """

    @classmethod
    def evaluate(
        cls,
        *,
        evidence: TemporalReoptimizationSafetyInput,
    ) -> TemporalReoptimizationSafetyResult:
        reasons: list[str] = []

        if evidence.calibration_state is None:
            reasons.append(
                "Temporal calibration evidence is missing."
            )

        if not evidence.affected_reservations:
            reasons.append(
                "Affected reservation temporal evidence is missing."
            )

        low_trust_reservations = [
            item
            for item in evidence.affected_reservations
            if (
                item.expected_turn_confidence
                != ExpectedTurnConfidence.HIGH
            )
        ]

        if low_trust_reservations:
            reasons.append(
                "Not every affected reservation has "
                "high expected-turn confidence."
            )

        if evidence.marginal_capacity_loss_ratio is None:
            reasons.append(
                "Marginal future capacity evidence is missing."
            )

        if evidence.lost_future_available_slots is None:
            reasons.append(
                "Future available-slot evidence is missing."
            )

        if reasons:
            return TemporalReoptimizationSafetyResult(
                context=None,
                complete=False,
                reasons=tuple(reasons),
            )

        context = TemporalAutopilotSafetyContext(
            calibration_state=(
                evidence.calibration_state
            ),
            expected_turn_confidence=(
                ExpectedTurnConfidence.HIGH
            ),
            marginal_capacity_loss_ratio=(
                evidence.marginal_capacity_loss_ratio
            ),
            lost_future_available_slots=(
                evidence.lost_future_available_slots
            ),
        )

        return TemporalReoptimizationSafetyResult(
            context=context,
            complete=True,
            reasons=(),
        )

    @classmethod
    def evaluate_guard(
        cls,
        *,
        evidence: TemporalReoptimizationSafetyInput,
    ):
        result = cls.evaluate(
            evidence=evidence,
        )

        return TemporalAutopilotGuardService.evaluate(
            context=result.context,
        )