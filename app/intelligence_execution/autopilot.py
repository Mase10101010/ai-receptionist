from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.intelligence_execution.schemas import (
    ExecutionEligibility,
    ExecutionEligibilityResult,
)


class AutopilotAuthorityService:
    def can_execute_automatically(
        self,
        *,
        execution_eligibility: ExecutionEligibilityResult | None,
        autopilot_enabled: bool,
    ) -> bool:
        if not autopilot_enabled:
            return False

        if execution_eligibility is None:
            return False

        return (
            execution_eligibility.eligibility
            == ExecutionEligibility.ELIGIBLE_FOR_AUTOMATIC_EXECUTION
        )

    def can_execute_stored_plan_automatically(
        self,
        *,
        plan: dict[str, Any] | None,
        autopilot_enabled: bool,
    ) -> bool:
        if not autopilot_enabled:
            return False

        if not plan:
            return False

        raw_execution_eligibility = plan.get(
            "execution_eligibility"
        )

        if not raw_execution_eligibility:
            return False

        try:
            execution_eligibility = (
                ExecutionEligibilityResult.model_validate(
                    raw_execution_eligibility
                )
            )
        except (
            PydanticValidationError,
            TypeError,
            ValueError,
        ):
            return False

        return self.can_execute_automatically(
            execution_eligibility=execution_eligibility,
            autopilot_enabled=autopilot_enabled,
        )