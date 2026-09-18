from __future__ import annotations

from datetime import datetime
from uuid import UUID

from .capacity_layers import (
    TemporalCapacityLayersService,
    TemporalDirectCapacitySignal,
)
from .future_capacity_snapshot import (
    TemporalFutureCapacitySnapshot,
    TemporalFutureCapacitySnapshotService,
)
from .live_intelligence import TemporalLiveIntelligence
from .schemas import FutureCapacityResponse
from .seat_release import (
    TemporalSeatReleaseForecastService,
    TemporalSeatReleaseProjection,
)
from .saturation import TemporalSaturationSlot


class TemporalFutureCapacityCoordinator:
    """
    Read-only composition adapter between established
    T1/T5 temporal truth and T6 future-capacity intelligence.

    Inputs:
    - T1 FutureCapacityResponse
    - T5 live intelligence keyed by occupied table
    - occupied table seat capacities

    Invariants:
    - does not call optimizer
    - does not query DB
    - does not regenerate turn predictions
    - does not write events
    - no commit / rollback
    - no Brain
    - no Autopilot

    T1 remains authoritative for direct bookability.
    T5 remains authoritative for expected/reliable release.
    """

    DEFAULT_PEAK_PERIOD_MINUTES = 60

    @classmethod
    def calculate(
        cls,
        *,
        evaluated_at: datetime,
        direct_capacity: FutureCapacityResponse,
        live_by_table: dict[
            UUID,
            TemporalLiveIntelligence,
        ],
        seat_capacity_by_table: dict[
            UUID,
            int,
        ],
        peak_period_minutes: int = (
            DEFAULT_PEAK_PERIOD_MINUTES
        ),
    ) -> TemporalFutureCapacitySnapshot:
        if peak_period_minutes <= 0:
            raise ValueError(
                "peak_period_minutes must be positive."
            )

        if direct_capacity.start_at < evaluated_at:
            raise ValueError(
                "Future capacity profile cannot start "
                "before evaluated_at."
            )

        projections = cls._build_release_projections(
            live_by_table=live_by_table,
            seat_capacity_by_table=(
                seat_capacity_by_table
            ),
        )

        release_forecast = (
            TemporalSeatReleaseForecastService
            .calculate(
                projections=projections,
                evaluated_at=evaluated_at,
            )
        )

        direct_signal = cls._build_direct_signal(
            direct_capacity
        )

        capacity_layers = (
            TemporalCapacityLayersService
            .calculate(
                direct=direct_signal,
                release_forecast=(
                    release_forecast
                ),
            )
        )

        saturation_slots = [
            TemporalSaturationSlot(
                slot_time=slot.start_at,
                directly_available=(
                    slot.directly_available
                ),
            )
            for slot in direct_capacity.slots
        ]

        peak_periods = cls._build_peak_periods(
            slots=saturation_slots,
            period_minutes=peak_period_minutes,
        )

        return (
            TemporalFutureCapacitySnapshotService
            .build(
                capacity=capacity_layers,
                saturation_slots=(
                    saturation_slots
                ),
                peak_periods=peak_periods,
            )
        )

    @staticmethod
    def _build_direct_signal(
        profile: FutureCapacityResponse,
    ) -> TemporalDirectCapacitySignal:
        current_slot = next(
            (
                slot
                for slot in profile.slots
                if slot.start_at
                == profile.start_at
            ),
            None,
        )

        if (
            current_slot is None
            or not current_slot.directly_available
        ):
            return TemporalDirectCapacitySignal(
                directly_available=False,
                assignment_capacity=None,
            )

        return TemporalDirectCapacitySignal(
            directly_available=True,
            assignment_capacity=(
                current_slot.assignment_capacity
            ),
        )

    @staticmethod
    def _build_release_projections(
        *,
        live_by_table: dict[
            UUID,
            TemporalLiveIntelligence,
        ],
        seat_capacity_by_table: dict[
            UUID,
            int,
        ],
    ) -> list[
        TemporalSeatReleaseProjection
    ]:
        projections: list[
            TemporalSeatReleaseProjection
        ] = []

        for table_id, live in (
            live_by_table.items()
        ):
            if (
                table_id
                not in seat_capacity_by_table
            ):
                raise ValueError(
                    "Missing seat capacity for live table."
                )

            seat_capacity = (
                seat_capacity_by_table[
                    table_id
                ]
            )

            if seat_capacity <= 0:
                raise ValueError(
                    "Live table seat capacity must "
                    "be positive."
                )

            window = live.release_window

            projections.append(
                TemporalSeatReleaseProjection(
                    table_id=table_id,
                    seat_capacity=seat_capacity,
                    expected_release_at=(
                        live.live_turn
                        .expected_release_at
                    ),
                    release_window_available=(
                        window.available
                    ),
                    release_window_start_at=(
                        window.window_start_at
                    ),
                    release_window_end_at=(
                        window.window_end_at
                    ),
                )
            )

        return projections

    @staticmethod
    def _build_peak_periods(
        *,
        slots: list[
            TemporalSaturationSlot
        ],
        period_minutes: int,
    ) -> list[
        list[
            TemporalSaturationSlot
        ]
    ]:
        if not slots:
            return []

        ordered = sorted(
            slots,
            key=lambda slot: slot.slot_time,
        )

        periods: list[
            list[
                TemporalSaturationSlot
            ]
        ] = []

        current: list[
            TemporalSaturationSlot
        ] = []

        period_start = ordered[0].slot_time

        for slot in ordered:
            elapsed_minutes = (
                slot.slot_time
                - period_start
            ).total_seconds() / 60

            if (
                current
                and elapsed_minutes
                >= period_minutes
            ):
                periods.append(current)
                current = []
                period_start = slot.slot_time

            current.append(slot)

        if current:
            periods.append(current)

        return periods