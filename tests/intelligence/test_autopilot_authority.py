from datetime import datetime, timezone
from uuid import uuid4

from app.intelligence_execution.autopilot import (
    AutopilotAuthorityService,
)
from app.intelligence_execution.schemas import (
    ExecutionEligibility,
    ExecutionEligibilityResult,
)


def build_eligibility(
    eligibility: ExecutionEligibility,
) -> ExecutionEligibilityResult:
    return ExecutionEligibilityResult(
        restaurant_id=uuid4(),
        reservation_id=uuid4(),
        eligibility=eligibility,
        reasons=[],
        generated_at=datetime.now(timezone.utc),
    )


def test_manager_confirmation_is_never_automatic_even_with_opt_in():
    service = AutopilotAuthorityService()

    result = service.can_execute_automatically(
        execution_eligibility=build_eligibility(
            ExecutionEligibility.MANAGER_CONFIRMATION_REQUIRED,
        ),
        autopilot_enabled=True,
    )

    assert result is False


def test_eligible_plan_is_not_automatic_without_opt_in():
    service = AutopilotAuthorityService()

    result = service.can_execute_automatically(
        execution_eligibility=build_eligibility(
            ExecutionEligibility.ELIGIBLE_FOR_AUTOMATIC_EXECUTION,
        ),
        autopilot_enabled=False,
    )

    assert result is False


def test_eligible_plan_is_automatic_with_explicit_opt_in():
    service = AutopilotAuthorityService()

    result = service.can_execute_automatically(
        execution_eligibility=build_eligibility(
            ExecutionEligibility.ELIGIBLE_FOR_AUTOMATIC_EXECUTION,
        ),
        autopilot_enabled=True,
    )

    assert result is True


def test_missing_eligibility_fails_closed():
    service = AutopilotAuthorityService()

    result = service.can_execute_automatically(
        execution_eligibility=None,
        autopilot_enabled=True,
    )

    assert result is False


def test_blocked_plan_is_never_automatic():
    service = AutopilotAuthorityService()

    result = service.can_execute_automatically(
        execution_eligibility=build_eligibility(
            ExecutionEligibility.BLOCKED,
        ),
        autopilot_enabled=True,
    )

    assert result is False

def test_stored_plan_eligible_with_opt_in_can_execute():
    result = build_eligibility(
        ExecutionEligibility.ELIGIBLE_FOR_AUTOMATIC_EXECUTION
    )

    plan = {
        "execution_eligibility": result.model_dump(
            mode="json"
        ),
    }

    assert (
        AutopilotAuthorityService()
        .can_execute_stored_plan_automatically(
            plan=plan,
            autopilot_enabled=True,
        )
        is True
    )


def test_stored_plan_eligible_without_opt_in_cannot_execute():
    result = build_eligibility(
        ExecutionEligibility.ELIGIBLE_FOR_AUTOMATIC_EXECUTION
    )

    plan = {
        "execution_eligibility": result.model_dump(
            mode="json"
        ),
    }

    assert (
        AutopilotAuthorityService()
        .can_execute_stored_plan_automatically(
            plan=plan,
            autopilot_enabled=False,
        )
        is False
    )


def test_stored_plan_missing_eligibility_cannot_execute():
    assert (
        AutopilotAuthorityService()
        .can_execute_stored_plan_automatically(
            plan={},
            autopilot_enabled=True,
        )
        is False
    )


def test_stored_plan_malformed_eligibility_cannot_execute():
    plan = {
        "execution_eligibility": {
            "eligibility": "not-a-real-state",
        },
    }

    assert (
        AutopilotAuthorityService()
        .can_execute_stored_plan_automatically(
            plan=plan,
            autopilot_enabled=True,
        )
        is False
    )