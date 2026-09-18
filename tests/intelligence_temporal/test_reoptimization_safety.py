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
from app.intelligence_temporal.reoptimization_safety import (
    TemporalAffectedReservationEvidence,
    TemporalReoptimizationSafetyInput,
    TemporalReoptimizationSafetyService,
)


def _reservation(
    confidence=ExpectedTurnConfidence.HIGH,
):
    return TemporalAffectedReservationEvidence(
        reservation_id=uuid4(),
        expected_turn_confidence=confidence,
    )


def _complete_evidence(
    *,
    calibration=(
        TemporalCalibrationState.WELL_CALIBRATED
    ),
    reservations=None,
    loss_ratio=0.0,
    lost_slots=0,
):
    return TemporalReoptimizationSafetyInput(
        calibration_state=calibration,
        affected_reservations=(
            tuple(reservations)
            if reservations is not None
            else (
                _reservation(),
                _reservation(),
            )
        ),
        marginal_capacity_loss_ratio=loss_ratio,
        lost_future_available_slots=lost_slots,
    )


def test_complete_safe_evidence_builds_context():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(),
        )
    )

    assert result.complete is True
    assert result.context is not None
    assert result.reasons == ()

    assert (
        result.context.expected_turn_confidence
        == ExpectedTurnConfidence.HIGH
    )


def test_missing_calibration_is_incomplete():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                calibration=None,
            ),
        )
    )

    assert result.complete is False
    assert result.context is None


def test_missing_affected_reservations_is_incomplete():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                reservations=[],
            ),
        )
    )

    assert result.complete is False
    assert result.context is None


def test_medium_confidence_reservation_is_incomplete():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                reservations=[
                    _reservation(),
                    _reservation(
                        ExpectedTurnConfidence.MEDIUM
                    ),
                ],
            ),
        )
    )

    assert result.complete is False
    assert result.context is None


def test_low_confidence_reservation_is_incomplete():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                reservations=[
                    _reservation(
                        ExpectedTurnConfidence.LOW
                    ),
                ],
            ),
        )
    )

    assert result.complete is False


def test_missing_marginal_loss_is_incomplete():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                loss_ratio=None,
            ),
        )
    )

    assert result.complete is False
    assert result.context is None


def test_missing_future_slots_is_incomplete():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                lost_slots=None,
            ),
        )
    )

    assert result.complete is False


def test_complete_risky_evidence_still_builds_context():
    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=_complete_evidence(
                loss_ratio=0.25,
                lost_slots=2,
            ),
        )
    )

    assert result.complete is True
    assert result.context is not None

    assert (
        result.context.marginal_capacity_loss_ratio
        == 0.25
    )
    assert (
        result.context.lost_future_available_slots
        == 2
    )


def test_complete_risky_evidence_is_vetoed_by_guard():
    evidence = _complete_evidence(
        loss_ratio=0.25,
        lost_slots=2,
    )

    result = (
        TemporalReoptimizationSafetyService
        .evaluate_guard(
            evidence=evidence,
        )
    )

    assert result.allowed is False


def test_complete_safe_evidence_passes_guard():
    evidence = _complete_evidence()

    result = (
        TemporalReoptimizationSafetyService
        .evaluate_guard(
            evidence=evidence,
        )
    )

    assert result.allowed is True


def test_complete_but_bad_calibration_is_vetoed():
    evidence = _complete_evidence(
        calibration=(
            TemporalCalibrationState
            .UNDERPREDICTING
        ),
    )

    composed = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=evidence,
        )
    )

    assert composed.complete is True

    guard = TemporalAutopilotGuardService.evaluate(
        context=composed.context,
    )

    assert guard.allowed is False


def test_multiple_high_confidence_reservations_supported():
    evidence = _complete_evidence(
        reservations=[
            _reservation(),
            _reservation(),
            _reservation(),
            _reservation(),
        ],
    )

    result = (
        TemporalReoptimizationSafetyService.evaluate(
            evidence=evidence,
        )
    )

    assert result.complete is True
    assert result.context is not None