from datetime import datetime, timezone
from uuid import uuid4

from app.intelligence_execution.schemas import (
    ExecutionEligibility,
    ExecutionEligibilityResult,
)
from app.intelligence_execution.temporal_autopilot import (
    TemporalAutopilotAuthorityService,
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


def _eligibility(
    state: ExecutionEligibility,
) -> ExecutionEligibilityResult:
    return ExecutionEligibilityResult(
        restaurant_id=uuid4(),
        reservation_id=uuid4(),
        eligibility=state,
        reasons=[],
        generated_at=datetime.now(timezone.utc),
    )


def _safe_temporal_context():
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


def _unsafe_temporal_context():
    return TemporalAutopilotSafetyContext(
        calibration_state=(
            TemporalCalibrationState.WELL_CALIBRATED
        ),
        expected_turn_confidence=(
            ExpectedTurnConfidence.HIGH
        ),
        marginal_capacity_loss_ratio=0.2,
        lost_future_available_slots=2,
    )


def test_existing_authority_and_safe_temporal_context_allows():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility
                .ELIGIBLE_FOR_AUTOMATIC_EXECUTION
            ),
            autopilot_enabled=True,
            temporal_context=_safe_temporal_context(),
        )
    )

    assert result.allowed is True
    assert result.existing_authority_allowed is True
    assert result.temporal_guard_allowed is True
    assert result.temporal_reasons == ()


def test_temporal_guard_can_veto_existing_authority():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility
                .ELIGIBLE_FOR_AUTOMATIC_EXECUTION
            ),
            autopilot_enabled=True,
            temporal_context=_unsafe_temporal_context(),
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is True
    assert result.temporal_guard_allowed is False
    assert result.temporal_reasons


def test_temporal_safety_cannot_grant_missing_opt_in():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility
                .ELIGIBLE_FOR_AUTOMATIC_EXECUTION
            ),
            autopilot_enabled=False,
            temporal_context=_safe_temporal_context(),
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is False
    assert result.temporal_guard_allowed is True


def test_temporal_safety_cannot_grant_manager_confirmation_plan():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility
                .MANAGER_CONFIRMATION_REQUIRED
            ),
            autopilot_enabled=True,
            temporal_context=_safe_temporal_context(),
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is False
    assert result.temporal_guard_allowed is True


def test_temporal_safety_cannot_grant_blocked_plan():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility.BLOCKED
            ),
            autopilot_enabled=True,
            temporal_context=_safe_temporal_context(),
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is False


def test_missing_execution_eligibility_fails_closed():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=None,
            autopilot_enabled=True,
            temporal_context=_safe_temporal_context(),
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is False


def test_missing_temporal_context_vetoes_existing_authority():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility
                .ELIGIBLE_FOR_AUTOMATIC_EXECUTION
            ),
            autopilot_enabled=True,
            temporal_context=None,
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is True
    assert result.temporal_guard_allowed is False
    assert result.temporal_reasons


def test_both_authorities_can_fail_independently():
    result = (
        TemporalAutopilotAuthorityService()
        .can_execute_automatically(
            execution_eligibility=_eligibility(
                ExecutionEligibility.BLOCKED
            ),
            autopilot_enabled=False,
            temporal_context=_unsafe_temporal_context(),
        )
    )

    assert result.allowed is False
    assert result.existing_authority_allowed is False
    assert result.temporal_guard_allowed is False