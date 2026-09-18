from __future__ import annotations

from pydantic import BaseModel

from .capacity_layers import (
    TemporalCapacityLayers,
)
from .capacity_pressure import (
    TemporalCapacityPressure,
    TemporalCapacityPressureService,
)
from .peak_periods import (
    TemporalPeakProfile,
    TemporalPeakPeriodService,
)
from .saturation import (
    TemporalSaturationService,
    TemporalSaturationSlot,
    TemporalSaturationSnapshot,
)


class TemporalFutureCapacitySnapshot(BaseModel):
    """
    Unified read-only temporal supply intelligence.

    Marginal candidate capacity is intentionally excluded:
    it is counterfactual and belongs to candidate evaluation,
    not restaurant-wide future capacity truth.
    """

    capacity: TemporalCapacityLayers
    pressure: TemporalCapacityPressure
    saturation: TemporalSaturationSnapshot
    peak_profile: TemporalPeakProfile


class TemporalFutureCapacitySnapshotService:
    """
    Pure composition service for T6 future-capacity signals.

    Inputs are already-established temporal truths.

    No DB.
    No event writes.
    No optimizer calls.
    No demand prediction.
    No Brain.
    No Autopilot.
    """

    @classmethod
    def build(
        cls,
        *,
        capacity: TemporalCapacityLayers,
        saturation_slots: list[
            TemporalSaturationSlot
        ],
        peak_periods: list[
            list[
                TemporalSaturationSlot
            ]
        ],
    ) -> TemporalFutureCapacitySnapshot:
        cls._validate_timeline(
            capacity=capacity,
            saturation_slots=saturation_slots,
        )

        pressure = (
            TemporalCapacityPressureService
            .calculate(
                capacity=capacity,
            )
        )

        saturation = (
            TemporalSaturationService
            .calculate(
                slots=saturation_slots,
            )
        )

        peak_profile = (
            TemporalPeakPeriodService
            .calculate(
                periods=peak_periods,
            )
        )

        return TemporalFutureCapacitySnapshot(
            capacity=capacity,
            pressure=pressure,
            saturation=saturation,
            peak_profile=peak_profile,
        )

    @staticmethod
    def _validate_timeline(
        *,
        capacity: TemporalCapacityLayers,
        saturation_slots: list[
            TemporalSaturationSlot
        ],
    ) -> None:
        if not capacity.layers:
            raise ValueError(
                "Future capacity snapshot requires "
                "at least one capacity layer."
            )

        if saturation_slots:
            earliest_slot = min(
                slot.slot_time
                for slot in saturation_slots
            )

            if (
                earliest_slot
                < capacity.evaluated_at
            ):
                raise ValueError(
                    "Future saturation slots cannot "
                    "precede evaluated_at."
                )