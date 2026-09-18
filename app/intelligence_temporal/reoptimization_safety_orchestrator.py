from __future__ import annotations

from pydantic import BaseModel

from .calibration_state import (
    TemporalCalibrationAssessment,
)
from .reoptimization_capacity_evidence import (
    TemporalReoptimizationCapacityEvidence,
)
from .reoptimization_safety import (
    TemporalReoptimizationSafetyInput,
    TemporalReoptimizationSafetyResult,
    TemporalReoptimizationSafetyService,
)
from .reoptimization_turn_evidence import (
    TemporalReoptimizationTurnEvidence,
)


class TemporalReoptimizationSafetyOrchestration(BaseModel):
    """
    Complete plan-level Temporal Autopilot safety evidence.

    This remains evidence/safety composition only.
    It does not grant automatic execution authority.
    """

    safety_input: TemporalReoptimizationSafetyInput
    safety_result: TemporalReoptimizationSafetyResult


class TemporalReoptimizationSafetyOrchestrator:
    """
    Pure composition root for one exact reoptimization plan.

    Pipeline:
        calibration assessment
        + affected-reservation turn evidence
        + marginal future-capacity evidence
            ->
        TemporalReoptimizationSafetyInput
            ->
        existing T8.4 safety composition

    Invariants:
    - no DB
    - no optimizer
    - no reoptimizer
    - no prediction
    - no capacity simulation
    - no calibration calculation
    - no persistence
    - no execution
    - no Autopilot authority grant
    - no Brain
    - no ML
    """

    @classmethod
    def evaluate(
        cls,
        *,
        calibration: TemporalCalibrationAssessment | None,
        turn_evidence: TemporalReoptimizationTurnEvidence | None,
        capacity_evidence: (
            TemporalReoptimizationCapacityEvidence | None
        ),
    ) -> TemporalReoptimizationSafetyOrchestration:
        safety_input = TemporalReoptimizationSafetyInput(
            calibration_state=(
                calibration.state
                if calibration is not None
                else None
            ),
            affected_reservations=(
                turn_evidence.affected_reservations
                if turn_evidence is not None
                else ()
            ),
            marginal_capacity_loss_ratio=(
                capacity_evidence
                .marginal_capacity_loss_ratio
                if capacity_evidence is not None
                else None
            ),
            lost_future_available_slots=(
                capacity_evidence
                .lost_future_available_slots
                if capacity_evidence is not None
                else None
            ),
        )

        safety_result = (
            TemporalReoptimizationSafetyService.evaluate(
                evidence=safety_input,
            )
        )

        return TemporalReoptimizationSafetyOrchestration(
            safety_input=safety_input,
            safety_result=safety_result,
        )