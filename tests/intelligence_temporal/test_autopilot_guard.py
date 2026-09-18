from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotGuardService,
    TemporalAutopilotSafetyContext,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)


def _safe_context(
    *,
    calibration_state=(
        TemporalCalibrationState.WELL_CALIBRATED
    ),
    confidence=ExpectedTurnConfidence.HIGH,
    loss_ratio=0.0,
    lost_slots=0,
):
    return TemporalAutopilotSafetyContext(
        calibration_state=calibration_state,
        expected_turn_confidence=confidence,
        marginal_capacity_loss_ratio=loss_ratio,
        lost_future_available_slots=lost_slots,
    )


def test_safe_temporal_context_does_not_veto():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(),
    )

    assert result.allowed is True
    assert result.reasons == ()


def test_missing_context_fails_closed():
    result = TemporalAutopilotGuardService.evaluate(
        context=None,
    )

    assert result.allowed is False
    assert result.reasons


def test_missing_calibration_fails_closed():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            calibration_state=None,
        ),
    )

    assert result.allowed is False


def test_non_well_calibrated_state_vetoes():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            calibration_state=(
                TemporalCalibrationState
                .INSUFFICIENT_DATA
            ),
        ),
    )

    assert result.allowed is False
    assert any(
        "calibration" in reason.lower()
        for reason in result.reasons
    )


def test_missing_prediction_confidence_fails_closed():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            confidence=None,
        ),
    )

    assert result.allowed is False


def test_medium_prediction_confidence_vetoes():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            confidence=ExpectedTurnConfidence.MEDIUM,
        ),
    )

    assert result.allowed is False


def test_low_prediction_confidence_vetoes():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            confidence=ExpectedTurnConfidence.LOW,
        ),
    )

    assert result.allowed is False


def test_unknown_future_slot_loss_fails_closed():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            lost_slots=None,
        ),
    )

    assert result.allowed is False


def test_known_future_slot_loss_vetoes():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            lost_slots=1,
        ),
    )

    assert result.allowed is False
    assert any(
        "future available slots" in reason.lower()
        for reason in result.reasons
    )


def test_unknown_marginal_capacity_loss_fails_closed():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            loss_ratio=None,
        ),
    )

    assert result.allowed is False


def test_positive_marginal_capacity_loss_vetoes():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            loss_ratio=0.1,
        ),
    )

    assert result.allowed is False
    assert any(
        "marginal" in reason.lower()
        for reason in result.reasons
    )


def test_multiple_unsafe_signals_accumulate_reasons():
    result = TemporalAutopilotGuardService.evaluate(
        context=_safe_context(
            calibration_state=(
                TemporalCalibrationState
                .INSUFFICIENT_DATA
            ),
            confidence=ExpectedTurnConfidence.LOW,
            loss_ratio=0.5,
            lost_slots=3,
        ),
    )

    assert result.allowed is False
    assert len(result.reasons) == 4