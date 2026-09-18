from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation

from .calibration_metrics import (
    TemporalCalibrationMetricsService,
)
from .calibration_state import (
    TemporalCalibrationStateService,
)
from .error_distribution import (
    TemporalErrorDistributionService,
)
from .live_signal import (
    TemporalLiveSignal,
    TemporalLiveSignalService,
)
from .live_turn import LiveTurnPrediction
from .live_turn_coordinator import LiveTurnCoordinator
from .outcome_reader import TemporalOutcomeEventReader
from .release_window import (
    TemporalReleaseWindow,
    TemporalReleaseWindowService,
)


class TemporalLiveIntelligence(BaseModel):
    live_turn: LiveTurnPrediction
    release_window: TemporalReleaseWindow
    signal: TemporalLiveSignal


class TemporalLiveIntelligenceCoordinator:
    """
    Read-only composition root for Alias live turn intelligence.

    Pipeline:
        SEATED reservation
            +
        original persisted prediction
            ->
        live turn
            +
        historical completed prediction outcomes
            ->
        calibration assessment
            +
        empirical error distribution
            ->
        reliable release window
            ->
        operational floor-map signal

    Invariants:
    - no new temporal prediction
    - no event writes
    - no persistence
    - no commit / rollback
    - no Brain
    - no optimizer
    - no Autopilot
    - missing live truth -> None
    - unreliable calibration -> point release only
    """

    def __init__(
        self,
        *,
        live_turn_coordinator: (
            LiveTurnCoordinator | None
        ) = None,
        outcome_reader: (
            TemporalOutcomeEventReader | None
        ) = None,
    ) -> None:
        self.live_turn_coordinator = (
            live_turn_coordinator
            or LiveTurnCoordinator()
        )

        self.outcome_reader = (
            outcome_reader
            or TemporalOutcomeEventReader()
        )

    async def calculate_for_reservation(
        self,
        *,
        session: AsyncSession,
        reservation: Reservation,
        evaluated_at: datetime,
    ) -> TemporalLiveIntelligence | None:
        live_turn = await (
            self.live_turn_coordinator
            .calculate_for_reservation(
                session=session,
                reservation=reservation,
                evaluated_at=evaluated_at,
            )
        )

        if live_turn is None:
            return None

        if reservation.restaurant_id is None:
            return None

        outcomes = await (
            self.outcome_reader
            .list_for_restaurant(
                session=session,
                restaurant_id=(
                    reservation.restaurant_id
                ),
            )
        )

        metrics = (
            TemporalCalibrationMetricsService
            .calculate(outcomes)
        )

        assessment = (
            TemporalCalibrationStateService
            .assess(metrics)
        )

        distribution = (
            TemporalErrorDistributionService
            .calculate(outcomes)
        )

        release_window = (
            TemporalReleaseWindowService
            .calculate(
                live_turn=live_turn,
                distribution=distribution,
                assessment=assessment,
            )
        )

        signal = TemporalLiveSignalService.calculate(
            live_turn=live_turn,
            release_window=release_window,
        )

        return TemporalLiveIntelligence(
            live_turn=live_turn,
            release_window=release_window,
            signal=signal,
        )