from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TemporalMarginalCapacitySlot(BaseModel):
    slot_time: datetime

    baseline_directly_available: bool
    candidate_directly_available: bool


class TemporalMarginalCapacityLoss(BaseModel):
    total_slots: int

    baseline_available_slots: int
    candidate_available_slots: int

    lost_available_slots: int
    gained_available_slots: int

    unchanged_available_slots: int
    unchanged_unavailable_slots: int

    marginal_loss_ratio: float

    first_capacity_loss_at: datetime | None
    last_capacity_loss_at: datetime | None


class TemporalMarginalCapacityService:
    """
    Measures deterministic counterfactual future capacity loss.

    Comparison:

        baseline future direct bookability
        versus
        future direct bookability after a candidate action.

    A lost slot is:

        baseline available
        AND
        candidate unavailable

    This service does NOT:
    - choose a table
    - rank candidates
    - call the optimizer
    - estimate demand
    - estimate revenue
    - assign monetary value
    - modify Brain
    - modify Autopilot

    It only measures the temporal opportunity cost signal
    that T7 may later consume.
    """

    @classmethod
    def calculate(
        cls,
        *,
        slots: list[
            TemporalMarginalCapacitySlot
        ],
    ) -> TemporalMarginalCapacityLoss:
        cls._validate_slots(
            slots
        )

        ordered = sorted(
            slots,
            key=lambda slot: (
                slot.slot_time
            ),
        )

        total_slots = len(ordered)

        baseline_available_slots = sum(
            1
            for slot in ordered
            if slot.baseline_directly_available
        )

        candidate_available_slots = sum(
            1
            for slot in ordered
            if slot.candidate_directly_available
        )

        lost_slots = [
            slot
            for slot in ordered
            if (
                slot.baseline_directly_available
                and not (
                    slot.candidate_directly_available
                )
            )
        ]

        gained_slots = [
            slot
            for slot in ordered
            if (
                not (
                    slot.baseline_directly_available
                )
                and slot.candidate_directly_available
            )
        ]

        unchanged_available_slots = sum(
            1
            for slot in ordered
            if (
                slot.baseline_directly_available
                and slot.candidate_directly_available
            )
        )

        unchanged_unavailable_slots = sum(
            1
            for slot in ordered
            if (
                not (
                    slot.baseline_directly_available
                )
                and not (
                    slot.candidate_directly_available
                )
            )
        )

        if baseline_available_slots == 0:
            marginal_loss_ratio = 0.0
        else:
            marginal_loss_ratio = (
                len(lost_slots)
                / baseline_available_slots
            )

        return TemporalMarginalCapacityLoss(
            total_slots=total_slots,
            baseline_available_slots=(
                baseline_available_slots
            ),
            candidate_available_slots=(
                candidate_available_slots
            ),
            lost_available_slots=len(
                lost_slots
            ),
            gained_available_slots=len(
                gained_slots
            ),
            unchanged_available_slots=(
                unchanged_available_slots
            ),
            unchanged_unavailable_slots=(
                unchanged_unavailable_slots
            ),
            marginal_loss_ratio=(
                marginal_loss_ratio
            ),
            first_capacity_loss_at=(
                lost_slots[0].slot_time
                if lost_slots
                else None
            ),
            last_capacity_loss_at=(
                lost_slots[-1].slot_time
                if lost_slots
                else None
            ),
        )

    @staticmethod
    def _validate_slots(
        slots: list[
            TemporalMarginalCapacitySlot
        ],
    ) -> None:
        slot_times = [
            slot.slot_time
            for slot in slots
        ]

        if (
            len(slot_times)
            != len(set(slot_times))
        ):
            raise ValueError(
                "Marginal capacity comparison cannot "
                "contain duplicate slot times."
            )