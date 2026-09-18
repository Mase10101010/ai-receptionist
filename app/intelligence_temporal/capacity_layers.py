from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .seat_release import (
    TemporalSeatReleaseForecast,
    TemporalSeatReleaseHorizon,
)


class TemporalDirectCapacitySignal(BaseModel):
    """
    Direct T1 capacity truth for one evaluated slot/request.

    assignment_capacity is intentionally NOT interpreted as
    total restaurant free seats.

    It is the capacity of the recommended direct assignment.
    """

    directly_available: bool
    assignment_capacity: int | None = None


class TemporalCapacityLayer(BaseModel):
    horizon_minutes: int

    directly_available_now: bool
    direct_assignment_capacity: int | None

    expected_released_tables: int
    expected_released_seats: int

    conservative_released_tables: int
    conservative_released_seats: int


class TemporalCapacityLayers(BaseModel):
    evaluated_at: datetime
    layers: list[TemporalCapacityLayer]


class TemporalCapacityLayersService:
    """
    Combines direct bookability truth with temporal release truth
    without falsely adding semantically different capacities.

    Important:

        direct_assignment_capacity
        != total currently free restaurant seats

    Therefore this service deliberately does NOT calculate:

        direct_assignment_capacity + released_seats

    No DB.
    No optimizer calls.
    No probability.
    No demand model.
    No Brain.
    No Autopilot.
    """

    @classmethod
    def calculate(
        cls,
        *,
        direct: TemporalDirectCapacitySignal,
        release_forecast: TemporalSeatReleaseForecast,
    ) -> TemporalCapacityLayers:
        cls._validate_direct_signal(
            direct
        )

        layers = [
            cls._build_layer(
                direct=direct,
                horizon=horizon,
            )
            for horizon in release_forecast.horizons
        ]

        return TemporalCapacityLayers(
            evaluated_at=release_forecast.evaluated_at,
            layers=layers,
        )

    @staticmethod
    def _build_layer(
        *,
        direct: TemporalDirectCapacitySignal,
        horizon: TemporalSeatReleaseHorizon,
    ) -> TemporalCapacityLayer:
        return TemporalCapacityLayer(
            horizon_minutes=horizon.horizon_minutes,
            directly_available_now=(
                direct.directly_available
            ),
            direct_assignment_capacity=(
                direct.assignment_capacity
            ),
            expected_released_tables=(
                horizon.expected_released_tables
            ),
            expected_released_seats=(
                horizon.expected_released_seats
            ),
            conservative_released_tables=(
                horizon.conservative_released_tables
            ),
            conservative_released_seats=(
                horizon.conservative_released_seats
            ),
        )

    @staticmethod
    def _validate_direct_signal(
        direct: TemporalDirectCapacitySignal,
    ) -> None:
        if (
            direct.directly_available
            and direct.assignment_capacity is None
        ):
            raise ValueError(
                "Directly available capacity requires "
                "an assignment capacity."
            )

        if (
            direct.assignment_capacity is not None
            and direct.assignment_capacity <= 0
        ):
            raise ValueError(
                "Direct assignment capacity must be positive."
            )

        if (
            not direct.directly_available
            and direct.assignment_capacity is not None
        ):
            raise ValueError(
                "Unavailable direct capacity cannot expose "
                "an assignment capacity."
            )