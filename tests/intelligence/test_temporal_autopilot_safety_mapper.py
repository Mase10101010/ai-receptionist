from app.intelligence.temporal_autopilot_safety_mapper import (
    IntelligenceTemporalAutopilotSafetyMapper,
)
from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotSafetyContext,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)


def _context():
    return TemporalAutopilotSafetyContext(
        calibration_state=(
            TemporalCalibrationState.WELL_CALIBRATED
        ),
        expected_turn_confidence=(
            ExpectedTurnConfidence.HIGH
        ),
        marginal_capacity_loss_ratio=0.0,
        lost_future_available_slots=0,
    )


def test_maps_temporal_safety_context():
    result = (
        IntelligenceTemporalAutopilotSafetyMapper
        .map(
            context=_context(),
        )
    )

    assert result is not None

    assert (
        result.calibration_state
        == "well_calibrated"
    )

    assert (
        result.expected_turn_confidence
        == "high"
    )

    assert (
        result.marginal_capacity_loss_ratio
        == 0.0
    )

    assert (
        result.lost_future_available_slots
        == 0
    )


def test_none_maps_to_none():
    assert (
        IntelligenceTemporalAutopilotSafetyMapper
        .map(
            context=None,
        )
        is None
    )


def test_mapper_does_not_expose_execution_authority():
    result = (
        IntelligenceTemporalAutopilotSafetyMapper
        .map(
            context=_context(),
        )
    )

    assert result is not None

    assert not hasattr(
        result,
        "allowed",
    )

    assert not hasattr(
        result,
        "execution_eligibility",
    )

    assert not hasattr(
        result,
        "autopilot_enabled",
    )