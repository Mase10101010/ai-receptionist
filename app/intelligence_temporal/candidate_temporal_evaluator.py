from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
)
from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    ScoredAssignment,
    TableCombination,
)

from .candidate_counterfactual import (
    TemporalCandidateCounterfactual,
    TemporalCandidateCounterfactualService,
)
from .counterfactual_capacity_runner import (
    TemporalCounterfactualCapacityRunner,
)
from .schemas import FutureCapacityRequest


class TemporalCandidateEvaluation(BaseModel):
    """
    Full temporal evaluation for one optimizer candidate.
    """

    candidate: IntelligenceAssignmentResponse
    counterfactual: TemporalCandidateCounterfactual
    occupancy_duration_minutes: int


class TemporalCandidateEvaluator:
    """
    Pure composition root for candidate temporal evaluation.

    Pipeline:
    optimizer-native candidate
        ->
    counterfactual capacity run
        ->
    marginal future capacity
        ->
    temporal candidate cost

    Invariants:
    - no DB
    - no persistence
    - no score mutation
    - no ranking
    - technical candidate start/end remain unchanged
    - temporal occupancy affects only the synthetic scenario
    - no Brain
    - no Autopilot
    - no ML
    """

    def __init__(
        self,
        *,
        capacity_runner: (
            TemporalCounterfactualCapacityRunner
            | None
        ) = None,
    ) -> None:
        self.capacity_runner = (
            capacity_runner
            or TemporalCounterfactualCapacityRunner()
        )

    def evaluate(
        self,
        *,
        request: FutureCapacityRequest,
        candidate: ScoredAssignment,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
        combinations: list[TableCombination] | None,
        candidate_party_size: int,
        candidate_occupancy_duration_minutes: int | None = None,
    ) -> TemporalCandidateEvaluation:
        profiles = self.capacity_runner.run(
            request=request,
            candidate=candidate,
            reservations=reservations,
            tables=tables,
            combinations=combinations,
            candidate_party_size=(
                candidate_party_size
            ),
            candidate_occupancy_duration_minutes=(
                candidate_occupancy_duration_minutes
            ),
        )

        candidate_response = (
            self._to_assignment_response(
                candidate=candidate,
                tables=tables,
            )
        )

        counterfactual = (
            TemporalCandidateCounterfactualService
            .evaluate(
                candidate=candidate_response,
                baseline=profiles.baseline,
                candidate_profile=(
                    profiles.candidate
                ),
            )
        )

        return TemporalCandidateEvaluation(
            candidate=candidate_response,
            counterfactual=counterfactual,
            occupancy_duration_minutes=(
                profiles
                .candidate_occupancy_duration_minutes
            ),
        )

    @staticmethod
    def _to_assignment_response(
        *,
        candidate: ScoredAssignment,
        tables: list[IntelligenceTable],
    ) -> IntelligenceAssignmentResponse:
        table_number_by_id = {
            table.id: table.table_number
            for table in tables
        }

        try:
            table_ids = [
                UUID(table_id)
                for table_id
                in candidate.candidate.table_ids
            ]
        except ValueError as exc:
            raise ValueError(
                "Optimizer table IDs must be valid UUIDs "
                "for temporal evaluation."
            ) from exc

        return IntelligenceAssignmentResponse(
            table_ids=table_ids,
            table_numbers=[
                table_number_by_id.get(
                    table_id,
                    table_id,
                )
                for table_id
                in candidate.candidate.table_ids
            ],
            start_at=(
                candidate.candidate.start_at
            ),
            end_at=(
                candidate.candidate.end_at
            ),
            capacity=(
                candidate.candidate.capacity
            ),
            score=candidate.score,
            seat_waste=candidate.seat_waste,
            fragmentation_minutes=(
                candidate.fragmentation_minutes
            ),
            explanation=candidate.explanation,
        )
