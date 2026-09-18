from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from .saturation import (
    TemporalSaturationService,
    TemporalSaturationSlot,
)


class TemporalPeakState(
    str,
    Enum,
):
    OFF_PEAK = "off_peak"
    BALANCED = "balanced"
    PEAK = "peak"


class TemporalPeakPeriod(BaseModel):
    start_at: datetime
    end_at: datetime

    total_slots: int
    unavailable_slots: int
    unavailable_ratio: float

    state: TemporalPeakState


class TemporalPeakProfile(BaseModel):
    periods: list[
        TemporalPeakPeriod
    ]


class TemporalPeakPeriodService:
    """
    Deterministic operational peak classification.

    This is NOT:
    - demand prediction
    - arrival forecast
    - occupancy probability
    - ML peak detection

    It classifies contiguous slot groups using direct
    bookability saturation only.

    No DB.
    No optimizer calls.
    No Brain.
    No Autopilot.
    """

    @classmethod
    def calculate(
        cls,
        *,
        periods: list[
            list[
                TemporalSaturationSlot
            ]
        ],
    ) -> TemporalPeakProfile:
        result: list[
            TemporalPeakPeriod
        ] = []

        for period_slots in periods:
            if not period_slots:
                continue

            ordered = sorted(
                period_slots,
                key=lambda slot: (
                    slot.slot_time
                ),
            )

            snapshot = (
                TemporalSaturationService
                .calculate(
                    slots=ordered,
                )
            )

            result.append(
                TemporalPeakPeriod(
                    start_at=(
                        ordered[0].slot_time
                    ),
                    end_at=(
                        ordered[-1].slot_time
                    ),
                    total_slots=(
                        snapshot.total_slots
                    ),
                    unavailable_slots=(
                        snapshot.unavailable_slots
                    ),
                    unavailable_ratio=(
                        snapshot.unavailable_ratio
                    ),
                    state=cls._classify(
                        snapshot.unavailable_ratio
                    ),
                )
            )

        return TemporalPeakProfile(
            periods=result,
        )

    @staticmethod
    def _classify(
        unavailable_ratio: float,
    ) -> TemporalPeakState:
        if unavailable_ratio >= 0.60:
            return TemporalPeakState.PEAK

        if unavailable_ratio >= 0.25:
            return TemporalPeakState.BALANCED

        return TemporalPeakState.OFF_PEAK