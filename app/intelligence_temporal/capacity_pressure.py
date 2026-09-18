from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .capacity_layers import (
    TemporalCapacityLayer,
    TemporalCapacityLayers,
)


class TemporalCapacityPressureState(
    str,
    Enum,
):
    CLEAR = "clear"
    RECOVERING_SOON = "recovering_soon"
    RECOVERING_LATER = "recovering_later"
    UNCERTAIN_RECOVERY = "uncertain_recovery"
    BLOCKED = "blocked"


class TemporalCapacityPressure(BaseModel):
    state: TemporalCapacityPressureState

    directly_available_now: bool

    first_expected_release_horizon_minutes: (
        int | None
    )

    first_conservative_release_horizon_minutes: (
        int | None
    )

    expected_released_seats_at_first_horizon: int
    conservative_released_seats_at_first_horizon: int


class TemporalCapacityPressureService:
    """
    Classifies temporal supply tightness.

    This is NOT demand pressure.

    It answers:
        how constrained is direct capacity,
        and how soon does occupied capacity return?

    Semantics:

    CLEAR
        direct capacity exists now.

    RECOVERING_SOON
        no direct capacity now, but reliable/conservative
        capacity returns within 30 minutes.

    RECOVERING_LATER
        no direct capacity now, but reliable/conservative
        capacity returns later in the forecast horizon.

    UNCERTAIN_RECOVERY
        expected capacity returns, but no reliable
        conservative release exists.

    BLOCKED
        no direct capacity and no expected release
        within the observed horizons.

    No DB.
    No demand model.
    No probability.
    No optimizer.
    No Brain.
    No Autopilot.
    """

    SOON_HORIZON_MINUTES = 30

    @classmethod
    def calculate(
        cls,
        *,
        capacity: TemporalCapacityLayers,
    ) -> TemporalCapacityPressure:
        if not capacity.layers:
            raise ValueError(
                "Temporal capacity pressure requires "
                "at least one capacity layer."
            )

        layers = sorted(
            capacity.layers,
            key=lambda layer: (
                layer.horizon_minutes
            ),
        )

        directly_available = any(
            layer.directly_available_now
            for layer in layers
        )

        if directly_available:
            return cls._build(
                state=(
                    TemporalCapacityPressureState.CLEAR
                ),
                directly_available=True,
                layers=layers,
            )

        first_conservative = (
            cls._first_conservative_release(
                layers
            )
        )

        if first_conservative is not None:
            if (
                first_conservative.horizon_minutes
                <= cls.SOON_HORIZON_MINUTES
            ):
                state = (
                    TemporalCapacityPressureState
                    .RECOVERING_SOON
                )
            else:
                state = (
                    TemporalCapacityPressureState
                    .RECOVERING_LATER
                )

            return cls._build(
                state=state,
                directly_available=False,
                layers=layers,
            )

        first_expected = (
            cls._first_expected_release(
                layers
            )
        )

        if first_expected is not None:
            return cls._build(
                state=(
                    TemporalCapacityPressureState
                    .UNCERTAIN_RECOVERY
                ),
                directly_available=False,
                layers=layers,
            )

        return cls._build(
            state=(
                TemporalCapacityPressureState.BLOCKED
            ),
            directly_available=False,
            layers=layers,
        )

    @staticmethod
    def _first_expected_release(
        layers: list[
            TemporalCapacityLayer
        ],
    ) -> TemporalCapacityLayer | None:
        return next(
            (
                layer
                for layer in layers
                if (
                    layer.expected_released_seats
                    > 0
                )
            ),
            None,
        )

    @staticmethod
    def _first_conservative_release(
        layers: list[
            TemporalCapacityLayer
        ],
    ) -> TemporalCapacityLayer | None:
        return next(
            (
                layer
                for layer in layers
                if (
                    layer.conservative_released_seats
                    > 0
                )
            ),
            None,
        )

    @classmethod
    def _build(
        cls,
        *,
        state: TemporalCapacityPressureState,
        directly_available: bool,
        layers: list[
            TemporalCapacityLayer
        ],
    ) -> TemporalCapacityPressure:
        first_expected = (
            cls._first_expected_release(
                layers
            )
        )

        first_conservative = (
            cls._first_conservative_release(
                layers
            )
        )

        return TemporalCapacityPressure(
            state=state,
            directly_available_now=(
                directly_available
            ),
            first_expected_release_horizon_minutes=(
                first_expected.horizon_minutes
                if first_expected is not None
                else None
            ),
            first_conservative_release_horizon_minutes=(
                first_conservative.horizon_minutes
                if first_conservative is not None
                else None
            ),
            expected_released_seats_at_first_horizon=(
                first_expected.expected_released_seats
                if first_expected is not None
                else 0
            ),
            conservative_released_seats_at_first_horizon=(
                first_conservative
                .conservative_released_seats
                if first_conservative is not None
                else 0
            ),
        )