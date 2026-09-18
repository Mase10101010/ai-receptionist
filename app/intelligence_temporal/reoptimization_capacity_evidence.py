from __future__ import annotations

from pydantic import BaseModel

from .marginal_capacity import (
    TemporalMarginalCapacityService,
    TemporalMarginalCapacitySlot,
)
from .reoptimization_capacity_runner import (
    TemporalReoptimizationCapacityRun,
)


class TemporalReoptimizationCapacityEvidence(BaseModel):
    """
    Marginal future-capacity evidence for one exact
    reoptimization plan.

    This is evidence only.
    It does not grant execution authority.
    """

    evaluated_slots: int

    baseline_available_slots: int
    candidate_available_slots: int

    lost_future_available_slots: int
    gained_future_available_slots: int

    marginal_capacity_loss_ratio: float


class TemporalReoptimizationCapacityEvidenceService:
    """
    Converts baseline/candidate future-capacity profiles into
    the existing T6.6 marginal-capacity semantics.

    Invariants:
    - no DB
    - no optimizer calls
    - no reoptimizer calls
    - no persistence
    - no ranking
    - no prediction
    - no calibration
    - no execution
    - no Brain
    - no ML
    """

    @classmethod
    def evaluate(
        cls,
        *,
        run: TemporalReoptimizationCapacityRun,
    ) -> TemporalReoptimizationCapacityEvidence:
        cls._validate_profiles(run=run)

        candidate_by_start = {
            slot.start_at: slot
            for slot in run.candidate.slots
        }

        marginal_slots = [
            TemporalMarginalCapacitySlot(
                slot_time=baseline_slot.start_at,
                baseline_directly_available=(
                    baseline_slot.directly_available
                ),
                candidate_directly_available=(
                    candidate_by_start[
                        baseline_slot.start_at
                    ].directly_available
                ),
            )
            for baseline_slot in run.baseline.slots
        ]

        marginal = (
            TemporalMarginalCapacityService
            .calculate(
                slots=marginal_slots,
            )
        )

        return TemporalReoptimizationCapacityEvidence(
            evaluated_slots=len(marginal_slots),
            baseline_available_slots=(
                marginal.baseline_available_slots
            ),
            candidate_available_slots=(
                marginal.candidate_available_slots
            ),
            lost_future_available_slots=(
                marginal.lost_available_slots
            ),
            gained_future_available_slots=(
                marginal.gained_available_slots
            ),
            marginal_capacity_loss_ratio=(
                marginal.marginal_loss_ratio
            ),
        )

    @staticmethod
    def _validate_profiles(
        *,
        run: TemporalReoptimizationCapacityRun,
    ) -> None:
        baseline = run.baseline
        candidate = run.candidate

        if baseline.restaurant_id != candidate.restaurant_id:
            raise ValueError(
                "Baseline and candidate restaurant IDs differ."
            )

        if baseline.start_at != candidate.start_at:
            raise ValueError(
                "Baseline and candidate start times differ."
            )

        if baseline.party_size != candidate.party_size:
            raise ValueError(
                "Baseline and candidate party sizes differ."
            )

        if (
            baseline.duration_minutes
            != candidate.duration_minutes
        ):
            raise ValueError(
                "Baseline and candidate durations differ."
            )

        if (
            baseline.horizon_minutes
            != candidate.horizon_minutes
        ):
            raise ValueError(
                "Baseline and candidate horizons differ."
            )

        if (
            baseline.slot_minutes
            != candidate.slot_minutes
        ):
            raise ValueError(
                "Baseline and candidate slot sizes differ."
            )

        baseline_times = {
            slot.start_at
            for slot in baseline.slots
        }

        candidate_times = {
            slot.start_at
            for slot in candidate.slots
        }

        if baseline_times != candidate_times:
            raise ValueError(
                "Baseline and candidate capacity slots "
                "are not aligned."
            )