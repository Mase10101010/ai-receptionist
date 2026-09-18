from __future__ import annotations

from pydantic import BaseModel

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
)

from .candidate_cost import (
    TemporalCandidateCost,
    TemporalCandidateCostService,
)
from .marginal_capacity import (
    TemporalMarginalCapacityService,
    TemporalMarginalCapacitySlot,
)
from .schemas import FutureCapacityResponse


class TemporalCandidateCounterfactual(BaseModel):
    """
    Counterfactual future-capacity evaluation for one
    existing optimizer candidate.

    baseline:
        future direct-bookability without applying
        the candidate action.

    candidate:
        future direct-bookability under the candidate
        scenario.

    This model does not create the candidate scenario.
    """

    cost: TemporalCandidateCost

    evaluated_slots: int
    baseline_available_slots: int
    candidate_available_slots: int


class TemporalCandidateCounterfactualService:
    """
    Pure evaluator over already-computed T1 profiles.

    Invariants:
    - no optimizer calls
    - no candidate generation
    - no DB
    - no persistence
    - no ranking
    - no score mutation
    - no Brain
    - no Autopilot
    """

    @classmethod
    def evaluate(
        cls,
        *,
        candidate: IntelligenceAssignmentResponse,
        baseline: FutureCapacityResponse,
        candidate_profile: FutureCapacityResponse,
    ) -> TemporalCandidateCounterfactual:
        cls._validate_profiles(
            baseline=baseline,
            candidate_profile=candidate_profile,
        )

        candidate_slots_by_start = {
            slot.start_at: slot
            for slot in candidate_profile.slots
        }

        slots = [
            TemporalMarginalCapacitySlot(
                slot_time=baseline_slot.start_at,
                baseline_directly_available=(
                    baseline_slot.directly_available
                ),
                candidate_directly_available=(
                    candidate_slots_by_start[
                        baseline_slot.start_at
                    ].directly_available
                ),
            )
            for baseline_slot in baseline.slots
        ]

        marginal_capacity = (
            TemporalMarginalCapacityService
            .calculate(
                slots=slots,
            )
        )

        cost = TemporalCandidateCostService.calculate(
            candidate=candidate,
            marginal_capacity=marginal_capacity,
        )

        return TemporalCandidateCounterfactual(
            cost=cost,
            evaluated_slots=len(slots),
            baseline_available_slots=(
                marginal_capacity
                .baseline_available_slots
            ),
            candidate_available_slots=(
                marginal_capacity
                .candidate_available_slots
            ),
        )

    @staticmethod
    def _validate_profiles(
        *,
        baseline: FutureCapacityResponse,
        candidate_profile: FutureCapacityResponse,
    ) -> None:
        if (
            baseline.restaurant_id
            != candidate_profile.restaurant_id
        ):
            raise ValueError(
                "Counterfactual profiles must belong "
                "to the same restaurant."
            )

        if baseline.start_at != candidate_profile.start_at:
            raise ValueError(
                "Counterfactual profiles must have "
                "the same start_at."
            )

        if (
            baseline.horizon_minutes
            != candidate_profile.horizon_minutes
        ):
            raise ValueError(
                "Counterfactual profiles must have "
                "the same horizon_minutes."
            )

        if (
            baseline.slot_minutes
            != candidate_profile.slot_minutes
        ):
            raise ValueError(
                "Counterfactual profiles must have "
                "the same slot_minutes."
            )

        if (
            baseline.duration_minutes
            != candidate_profile.duration_minutes
        ):
            raise ValueError(
                "Counterfactual profiles must have "
                "the same duration_minutes."
            )

        if baseline.party_size != candidate_profile.party_size:
            raise ValueError(
                "Counterfactual profiles must have "
                "the same party_size."
            )

        baseline_times = [
            slot.start_at
            for slot in baseline.slots
        ]

        candidate_times = [
            slot.start_at
            for slot in candidate_profile.slots
        ]

        if len(baseline_times) != len(
            set(baseline_times)
        ):
            raise ValueError(
                "Baseline profile contains duplicate "
                "slot times."
            )

        if len(candidate_times) != len(
            set(candidate_times)
        ):
            raise ValueError(
                "Candidate profile contains duplicate "
                "slot times."
            )

        if set(baseline_times) != set(
            candidate_times
        ):
            raise ValueError(
                "Counterfactual profiles must contain "
                "the same slot times."
            )