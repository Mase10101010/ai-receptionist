from __future__ import annotations

from datetime import datetime, timezone

from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.live_signal import (
    TemporalLiveSignalService,
    TemporalLiveSignalState,
)
from app.intelligence_temporal.live_turn import (
    LiveTurnPrediction,
    LiveTurnState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.release_window import (
    TemporalReleaseWindow,
)


EXPECTED_RELEASE = datetime(
    2026,
    9,
    6,
    20,
    40,
    tzinfo=timezone.utc,
)


def _live_turn(
    *,
    remaining_minutes: int,
    overrun_minutes: int = 0,
    state: LiveTurnState = (
        LiveTurnState.IN_PROGRESS
    ),
) -> LiveTurnPrediction:
    return LiveTurnPrediction(
        seated_at=datetime(
            2026,
            9,
            6,
            19,
            0,
            tzinfo=timezone.utc,
        ),
        evaluated_at=datetime(
            2026,
            9,
            6,
            19,
            30,
            tzinfo=timezone.utc,
        ),
        expected_duration_minutes=100,
        expected_release_at=EXPECTED_RELEASE,
        elapsed_minutes=30,
        remaining_minutes=remaining_minutes,
        overrun_minutes=overrun_minutes,
        state=state,
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


def _release_window(
    *,
    available: bool = True,
) -> TemporalReleaseWindow:
    return TemporalReleaseWindow(
        expected_release_at=EXPECTED_RELEASE,
        window_start_at=(
            datetime(
                2026,
                9,
                6,
                20,
                30,
                tzinfo=timezone.utc,
            )
            if available
            else None
        ),
        window_end_at=(
            datetime(
                2026,
                9,
                6,
                20,
                55,
                tzinfo=timezone.utc,
            )
            if available
            else None
        ),
        available=available,
        sample_count=30,
        calibration_state=(
            TemporalCalibrationState.WELL_CALIBRATED
        ),
    )


def test_turn_is_in_service_when_release_is_not_near():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=30,
        ),
        release_window=_release_window(),
    )

    assert (
        signal.state
        == TemporalLiveSignalState.IN_SERVICE
    )


def test_turn_is_expected_to_free_soon_at_threshold():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=15,
        ),
        release_window=_release_window(),
    )

    assert (
        signal.state
        == (
            TemporalLiveSignalState
            .EXPECTED_TO_FREE_SOON
        )
    )


def test_turn_is_expected_to_free_soon_inside_threshold():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=5,
        ),
        release_window=_release_window(),
    )

    assert (
        signal.state
        == (
            TemporalLiveSignalState
            .EXPECTED_TO_FREE_SOON
        )
    )


def test_expected_release_boundary_has_priority():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=0,
            state=(
                LiveTurnState
                .EXPECTED_RELEASE_REACHED
            ),
        ),
        release_window=_release_window(),
    )

    assert (
        signal.state
        == (
            TemporalLiveSignalState
            .EXPECTED_RELEASE_REACHED
        )
    )


def test_overrun_has_priority_over_remaining_time():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=0,
            overrun_minutes=12,
            state=LiveTurnState.OVERRUN,
        ),
        release_window=_release_window(),
    )

    assert (
        signal.state
        == TemporalLiveSignalState.OVERRUN
    )

    assert signal.overrun_minutes == 12


def test_release_window_is_exposed_when_available():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=10,
        ),
        release_window=_release_window(
            available=True,
        ),
    )

    assert signal.release_window_available is True

    assert signal.release_window_start_at == datetime(
        2026,
        9,
        6,
        20,
        30,
        tzinfo=timezone.utc,
    )

    assert signal.release_window_end_at == datetime(
        2026,
        9,
        6,
        20,
        55,
        tzinfo=timezone.utc,
    )


def test_unreliable_window_is_not_exposed():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=10,
        ),
        release_window=_release_window(
            available=False,
        ),
    )

    assert signal.release_window_available is False
    assert signal.release_window_start_at is None
    assert signal.release_window_end_at is None


def test_expected_release_truth_is_preserved():
    signal = TemporalLiveSignalService.calculate(
        live_turn=_live_turn(
            remaining_minutes=30,
        ),
        release_window=_release_window(),
    )

    assert (
        signal.expected_release_at
        == EXPECTED_RELEASE
    )