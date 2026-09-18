from types import SimpleNamespace
from uuid import uuid4

from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotGuardService,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)
from app.intelligence_temporal.reoptimization_capacity_evidence import (
    TemporalReoptimizationCapacityEvidence,
)
from app.intelligence_temporal.reoptimization_safety import (
    TemporalAffectedReservationEvidence,
)
from app.intelligence_temporal.reoptimization_safety_orchestrator import (
    TemporalReoptimizationSafetyOrchestrator,
)
from app.intelligence_temporal.reoptimization_turn_evidence import (
    TemporalReoptimizationTurnEvidence,
)


def _calibration(
    state=TemporalCalibrationState.WELL_CALIBRATED,
):
    return SimpleNamespace(
        state=state,
    )


def _turn_evidence(
    *confidences,
):
    return TemporalReoptimizationTurnEvidence(
        affected_reservations=tuple(
            TemporalAffectedReservationEvidence(
                reservation_id=uuid4(),
                expected_turn_confidence=confidence,
            )
            for confidence in confidences
        ),
    )


def _capacity_evidence(
    *,
    loss_ratio=0.0,
    lost_slots=0,
):
    return TemporalReoptimizationCapacityEvidence(
        evaluated_slots=4,
        baseline_available_slots=4,
        candidate_available_slots=(
            4 - lost_slots
        ),
        lost_future_available_slots=lost_slots,
        gained_future_available_slots=0,
        marginal_capacity_loss_ratio=loss_ratio,
    )


def test_complete_safe_evidence_builds_complete_context():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(),
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
                ExpectedTurnConfidence.HIGH,
            ),
            capacity_evidence=_capacity_evidence(),
        )
    )

    assert result.safety_result.complete is True
    assert result.safety_result.context is not None

    assert (
        result.safety_result.context.calibration_state
        == TemporalCalibrationState.WELL_CALIBRATED
    )

    assert (
        result.safety_result.context
        .expected_turn_confidence
        == ExpectedTurnConfidence.HIGH
    )

    assert (
        result.safety_result.context
        .lost_future_available_slots
        == 0
    )

    assert (
        result.safety_result.context
        .marginal_capacity_loss_ratio
        == 0.0
    )


def test_missing_calibration_is_incomplete():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=None,
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
            ),
            capacity_evidence=_capacity_evidence(),
        )
    )

    assert result.safety_result.complete is False
    assert result.safety_result.context is None


def test_missing_turn_evidence_is_incomplete():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(),
            turn_evidence=None,
            capacity_evidence=_capacity_evidence(),
        )
    )

    assert result.safety_result.complete is False
    assert result.safety_result.context is None


def test_missing_capacity_evidence_is_incomplete():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(),
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
            ),
            capacity_evidence=None,
        )
    )

    assert result.safety_result.complete is False
    assert result.safety_result.context is None


def test_mixed_turn_confidence_is_incomplete():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(),
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
                ExpectedTurnConfidence.MEDIUM,
            ),
            capacity_evidence=_capacity_evidence(),
        )
    )

    assert result.safety_result.complete is False
    assert result.safety_result.context is None


def test_capacity_loss_can_be_complete_but_unsafe():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(),
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
            ),
            capacity_evidence=_capacity_evidence(
                loss_ratio=0.25,
                lost_slots=1,
            ),
        )
    )

    assert result.safety_result.complete is True
    assert result.safety_result.context is not None

    guard = TemporalAutopilotGuardService.evaluate(
        context=result.safety_result.context,
    )

    assert guard.allowed is False


def test_non_well_calibrated_can_be_complete_but_unsafe():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(
                TemporalCalibrationState.UNDERPREDICTING,
            ),
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
            ),
            capacity_evidence=_capacity_evidence(),
        )
    )

    assert result.safety_result.complete is True
    assert result.safety_result.context is not None

    guard = TemporalAutopilotGuardService.evaluate(
        context=result.safety_result.context,
    )

    assert guard.allowed is False


def test_orchestrator_does_not_grant_execution_authority():
    result = (
        TemporalReoptimizationSafetyOrchestrator
        .evaluate(
            calibration=_calibration(),
            turn_evidence=_turn_evidence(
                ExpectedTurnConfidence.HIGH,
            ),
            capacity_evidence=_capacity_evidence(),
        )
    )

    assert not hasattr(result, "allowed")
    assert not hasattr(
        result,
        "execution_eligibility",
    )
    assert not hasattr(
        result,
        "autopilot_enabled",
    )