from __future__ import annotations

from app.intelligence_temporal.calibration_metrics import (
    TemporalAccuracyMetrics,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
    TemporalCalibrationStateService,
)


def _metrics(
    *,
    sample_count: int = 20,
    mae: float | None = 5.0,
    signed_error: float | None = 0.0,
) -> TemporalAccuracyMetrics:
    return TemporalAccuracyMetrics(
        sample_count=sample_count,
        mean_absolute_error_minutes=mae,
        mean_signed_error_minutes=signed_error,
        underprediction_count=0,
        underprediction_rate=0.0,
        overprediction_count=0,
        overprediction_rate=0.0,
        exact_count=0,
        exact_rate=0.0,
        within_5_minutes_count=0,
        within_5_minutes_rate=0.0,
        within_10_minutes_count=0,
        within_10_minutes_rate=0.0,
    )


def test_insufficient_data_below_minimum_sample_count():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=14,
                mae=1,
                signed_error=0,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .INSUFFICIENT_DATA
    )


def test_minimum_sample_count_is_mature():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=15,
                mae=4,
                signed_error=1,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .WELL_CALIBRATED
    )


def test_high_absolute_error_is_unreliable_even_without_bias():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=18,
                signed_error=0,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .UNRELIABLE
    )


def test_systematic_positive_error_is_underpredicting():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=8,
                signed_error=6,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .UNDERPREDICTING
    )


def test_systematic_negative_error_is_overpredicting():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=8,
                signed_error=-6,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .OVERPREDICTING
    )


def test_acceptable_accuracy_without_material_bias_is_well_calibrated():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=7,
                signed_error=2,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .WELL_CALIBRATED
    )


def test_bias_boundary_is_inclusive():
    under = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=7,
                signed_error=5,
            )
        )
    )

    over = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=7,
                signed_error=-5,
            )
        )
    )

    assert (
        under.state
        == TemporalCalibrationState
        .UNDERPREDICTING
    )

    assert (
        over.state
        == TemporalCalibrationState
        .OVERPREDICTING
    )


def test_unreliable_takes_precedence_over_directional_bias():
    assessment = (
        TemporalCalibrationStateService.assess(
            _metrics(
                sample_count=30,
                mae=25,
                signed_error=12,
            )
        )
    )

    assert (
        assessment.state
        == TemporalCalibrationState
        .UNRELIABLE
    )