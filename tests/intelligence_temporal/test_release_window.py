from __future__ import annotations

from datetime import datetime, timezone

from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationAssessment,
    TemporalCalibrationState,
)
from app.intelligence_temporal.error_distribution import (
    TemporalErrorDistribution,
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
    TemporalReleaseWindowService,
)


def _live_turn() -> LiveTurnPrediction:
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
        expected_release_at=datetime(
            2026,
            9,
            6,
            20,
            40,
            tzinfo=timezone.utc,
        ),
        elapsed_minutes=30,
        remaining_minutes=70,
        overrun_minutes=0,
        state=LiveTurnState.IN_PROGRESS,
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=ExpectedTurnConfidence.HIGH,
        used_learned_pattern=True,
    )


def _assessment(
    state: TemporalCalibrationState = (
        TemporalCalibrationState.WELL_CALIBRATED
    ),
    sample_count: int = 30,
) -> TemporalCalibrationAssessment:
    return TemporalCalibrationAssessment(
        state=state,
        sample_count=sample_count,
        mean_absolute_error_minutes=8.0,
        mean_signed_error_minutes=1.0,
    )


def _distribution(
    *,
    sample_count: int = 30,
    p10: int | None = -10,
    p50: int | None = 0,
    p90: int | None = 15,
) -> TemporalErrorDistribution:
    return TemporalErrorDistribution(
        sample_count=sample_count,
        p10_signed_error_minutes=p10,
        p50_signed_error_minutes=p50,
        p90_signed_error_minutes=p90,
    )


def test_builds_release_window_from_empirical_errors():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(),
        assessment=_assessment(),
    )

    assert result.available is True

    assert result.window_start_at == datetime(
        2026,
        9,
        6,
        20,
        30,
        tzinfo=timezone.utc,
    )

    assert result.window_end_at == datetime(
        2026,
        9,
        6,
        20,
        55,
        tzinfo=timezone.utc,
    )

    assert result.sample_count == 30

    assert (
        result.calibration_state
        == TemporalCalibrationState.WELL_CALIBRATED
    )


def test_sparse_distribution_does_not_expose_window():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(
            sample_count=14,
        ),
        assessment=_assessment(
            sample_count=14,
        ),
    )

    assert result.available is False
    assert result.window_start_at is None
    assert result.window_end_at is None


def test_underpredicting_state_does_not_expose_window():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(),
        assessment=_assessment(
            TemporalCalibrationState.UNDERPREDICTING
        ),
    )

    assert result.available is False


def test_overpredicting_state_does_not_expose_window():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(),
        assessment=_assessment(
            TemporalCalibrationState.OVERPREDICTING
        ),
    )

    assert result.available is False


def test_unreliable_state_does_not_expose_window():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(),
        assessment=_assessment(
            TemporalCalibrationState.UNRELIABLE
        ),
    )

    assert result.available is False


def test_insufficient_calibration_does_not_expose_window():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(),
        assessment=_assessment(
            TemporalCalibrationState.INSUFFICIENT_DATA
        ),
    )

    assert result.available is False


def test_missing_quantile_does_not_expose_window():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(
            p90=None,
        ),
        assessment=_assessment(),
    )

    assert result.available is False


def test_invalid_quantile_order_fails_closed():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(
            p10=20,
            p90=-10,
        ),
        assessment=_assessment(),
    )

    assert result.available is False


def test_expected_release_is_preserved_when_window_unavailable():
    result = TemporalReleaseWindowService.calculate(
        live_turn=_live_turn(),
        distribution=_distribution(
            sample_count=5,
        ),
        assessment=_assessment(
            TemporalCalibrationState.INSUFFICIENT_DATA,
            sample_count=5,
        ),
    )

    assert result.available is False

    assert result.expected_release_at == datetime(
        2026,
        9,
        6,
        20,
        40,
        tzinfo=timezone.utc,
    )