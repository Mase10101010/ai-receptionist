from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    ReoptimizationPlan,
    TableCombination,
)

from .autopilot_guard import (
    TemporalAutopilotSafetyContext,
)
from .calibration_state import (
    TemporalCalibrationAssessment,
)
from .reoptimization_capacity_evidence import (
    TemporalReoptimizationCapacityEvidence,
    TemporalReoptimizationCapacityEvidenceService,
)
from .reoptimization_capacity_runner import (
    TemporalReoptimizationCapacityRunner,
)
from .reoptimization_safety_orchestrator import (
    TemporalReoptimizationSafetyOrchestration,
    TemporalReoptimizationSafetyOrchestrator,
)
from .reoptimization_turn_evidence import (
    TemporalReoptimizationTurnEvidence,
    TemporalReoptimizationTurnEvidenceService,
)
from .schemas import FutureCapacityRequest
from .snapshot import TemporalLearningSnapshot


class TemporalReoptimizationSafetyResolution(BaseModel):
    """
    Complete temporal safety resolution for one exact
    reoptimization plan.

    This is evidence only.
    It does not grant automatic execution authority.
    """

    turn_evidence: TemporalReoptimizationTurnEvidence

    capacity_evidence: (
        TemporalReoptimizationCapacityEvidence
    )

    orchestration: (
        TemporalReoptimizationSafetyOrchestration
    )

    context: TemporalAutopilotSafetyContext | None


class TemporalReoptimizationSafetyResolver:
    """
    Pure composition root over already-loaded production truth.

    Pipeline:
        exact ReoptimizationPlan
        + baseline reservations
        + tables/combinations
        + temporal learning snapshot
        + temporal calibration assessment
            ->
        future-capacity counterfactual
            ->
        marginal capacity evidence
            +
        affected-reservation turn evidence
            ->
        plan-level safety composition

    Invariants:
    - no DB
    - no persistence
    - no reoptimizer calls
    - no high-level optimizer calls
    - no ranking
    - no score mutation
    - no execution
    - no Autopilot authority grant
    - no Brain
    - no ML
    """

    def __init__(
        self,
        *,
        capacity_runner: (
            TemporalReoptimizationCapacityRunner
            | None
        ) = None,
    ) -> None:
        self.capacity_runner = (
            capacity_runner
            or TemporalReoptimizationCapacityRunner()
        )

    def resolve(
        self,
        *,
        plan: ReoptimizationPlan,
        new_reservation_id: UUID,
        new_reservation_party_size: int,
        capacity_request: FutureCapacityRequest,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
        combinations: list[TableCombination] | None,
        learning_snapshot: TemporalLearningSnapshot,
        calibration: TemporalCalibrationAssessment | None,
    ) -> TemporalReoptimizationSafetyResolution:
        capacity_run = self.capacity_runner.run(
            request=capacity_request,
            plan=plan,
            reservations=reservations,
            tables=tables,
            combinations=combinations,
            new_reservation_id=str(
                new_reservation_id
            ),
            new_reservation_party_size=(
                new_reservation_party_size
            ),
        )

        capacity_evidence = (
            TemporalReoptimizationCapacityEvidenceService
            .evaluate(
                run=capacity_run,
            )
        )

        turn_evidence = (
            TemporalReoptimizationTurnEvidenceService
            .evaluate(
                plan=plan,
                new_reservation_id=(
                    new_reservation_id
                ),
                new_reservation_party_size=(
                    new_reservation_party_size
                ),
                snapshot=learning_snapshot,
                tables=tables,
            )
        )

        orchestration = (
            TemporalReoptimizationSafetyOrchestrator
            .evaluate(
                calibration=calibration,
                turn_evidence=turn_evidence,
                capacity_evidence=capacity_evidence,
            )
        )

        return TemporalReoptimizationSafetyResolution(
            turn_evidence=turn_evidence,
            capacity_evidence=capacity_evidence,
            orchestration=orchestration,
            context=(
                orchestration
                .safety_result
                .context
            ),
        )