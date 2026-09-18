from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from .live_turn import (
    LiveTurnPrediction,
    LiveTurnState,
)
from .release_window import (
    TemporalReleaseWindow,
)


class TemporalLiveSignalState(str, Enum):
    IN_SERVICE = "in_service"
    EXPECTED_TO_FREE_SOON = (
        "expected_to_free_soon"
    )
    EXPECTED_RELEASE_REACHED = (
        "expected_release_reached"
    )
    OVERRUN = "overrun"


class TemporalLiveSignal(BaseModel):
    state: TemporalLiveSignalState

    expected_release_at: datetime

    remaining_minutes: int
    overrun_minutes: int

    release_window_available: bool
    release_window_start_at: datetime | None
    release_window_end_at: datetime | None


class TemporalLiveSignalService:
    """
    Converts temporal truth into an operational floor-map signal.

    EXPECTED_TO_FREE_SOON means only:
        expected remaining time <= FREE_SOON_MINUTES

    It is not a probabilistic claim.

    No DB access.
    No persistence.
    No Brain.
    No optimizer.
    No Autopilot.
    """

    FREE_SOON_MINUTES = 15

    @classmethod
    def calculate(
        cls,
        *,
        live_turn: LiveTurnPrediction,
        release_window: TemporalReleaseWindow,
    ) -> TemporalLiveSignal:
        if live_turn.state == LiveTurnState.OVERRUN:
            state = TemporalLiveSignalState.OVERRUN

        elif (
            live_turn.state
            == LiveTurnState.EXPECTED_RELEASE_REACHED
        ):
            state = (
                TemporalLiveSignalState
                .EXPECTED_RELEASE_REACHED
            )

        elif (
            live_turn.remaining_minutes
            <= cls.FREE_SOON_MINUTES
        ):
            state = (
                TemporalLiveSignalState
                .EXPECTED_TO_FREE_SOON
            )

        else:
            state = TemporalLiveSignalState.IN_SERVICE

        return TemporalLiveSignal(
            state=state,
            expected_release_at=(
                live_turn.expected_release_at
            ),
            remaining_minutes=(
                live_turn.remaining_minutes
            ),
            overrun_minutes=(
                live_turn.overrun_minutes
            ),
            release_window_available=(
                release_window.available
            ),
            release_window_start_at=(
                release_window.window_start_at
            ),
            release_window_end_at=(
                release_window.window_end_at
            ),
        )