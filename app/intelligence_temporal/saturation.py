from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TemporalSaturationState(
    str,
    Enum,
):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    FULL = "full"


class TemporalSaturationSlot(BaseModel):
    slot_time: datetime
    directly_available: bool


class TemporalSaturationSnapshot(BaseModel):
    total_slots: int

    available_slots: int
    unavailable_slots: int

    unavailable_ratio: float

    state: TemporalSaturationState

    first_unavailable_at: datetime | None
    first_available_at: datetime | None

    longest_unavailable_run: int


class TemporalSaturationService:
    """
    Deterministic future direct-bookability saturation.

    This is NOT:
    - demand probability
    - occupancy probability
    - forecasted revenue pressure
    - ML saturation prediction

    It measures only how frequently evaluated future
    slots are directly unavailable.

    No DB.
    No optimizer calls.
    No Brain.
    No Autopilot.
    """

    MODERATE_THRESHOLD = 0.25
    HIGH_THRESHOLD = 0.60

    @classmethod
    def calculate(
        cls,
        *,
        slots: list[
            TemporalSaturationSlot
        ],
    ) -> TemporalSaturationSnapshot:
        cls._validate_slots(
            slots
        )

        total_slots = len(slots)

        if total_slots == 0:
            return TemporalSaturationSnapshot(
                total_slots=0,
                available_slots=0,
                unavailable_slots=0,
                unavailable_ratio=0.0,
                state=TemporalSaturationState.LOW,
                first_unavailable_at=None,
                first_available_at=None,
                longest_unavailable_run=0,
            )

        ordered = sorted(
            slots,
            key=lambda slot: slot.slot_time,
        )

        available_slots = sum(
            1
            for slot in ordered
            if slot.directly_available
        )

        unavailable_slots = (
            total_slots
            - available_slots
        )

        unavailable_ratio = (
            unavailable_slots
            / total_slots
        )

        first_unavailable = next(
            (
                slot.slot_time
                for slot in ordered
                if not slot.directly_available
            ),
            None,
        )

        first_available = next(
            (
                slot.slot_time
                for slot in ordered
                if slot.directly_available
            ),
            None,
        )

        longest_unavailable_run = (
            cls._longest_unavailable_run(
                ordered
            )
        )

        state = cls._classify(
            unavailable_ratio=unavailable_ratio,
        )

        return TemporalSaturationSnapshot(
            total_slots=total_slots,
            available_slots=available_slots,
            unavailable_slots=unavailable_slots,
            unavailable_ratio=unavailable_ratio,
            state=state,
            first_unavailable_at=first_unavailable,
            first_available_at=first_available,
            longest_unavailable_run=(
                longest_unavailable_run
            ),
        )

    @classmethod
    def _classify(
        cls,
        *,
        unavailable_ratio: float,
    ) -> TemporalSaturationState:
        if unavailable_ratio >= 1.0:
            return TemporalSaturationState.FULL

        if (
            unavailable_ratio
            >= cls.HIGH_THRESHOLD
        ):
            return TemporalSaturationState.HIGH

        if (
            unavailable_ratio
            >= cls.MODERATE_THRESHOLD
        ):
            return TemporalSaturationState.MODERATE

        return TemporalSaturationState.LOW

    @staticmethod
    def _longest_unavailable_run(
        slots: list[
            TemporalSaturationSlot
        ],
    ) -> int:
        longest = 0
        current = 0

        for slot in slots:
            if not slot.directly_available:
                current += 1
                longest = max(
                    longest,
                    current,
                )
            else:
                current = 0

        return longest

    @staticmethod
    def _validate_slots(
        slots: list[
            TemporalSaturationSlot
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
                "Temporal saturation cannot contain "
                "duplicate slot times."
            )