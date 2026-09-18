from __future__ import annotations

from pydantic import BaseModel

from app.intelligence_execution.autopilot import (
    AutopilotAuthorityService,
)
from app.intelligence_execution.schemas import (
    ExecutionEligibilityResult,
)
from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotGuardResult,
    TemporalAutopilotGuardService,
    TemporalAutopilotSafetyContext,
)


class TemporalAutopilotAuthorityResult(BaseModel):
    allowed: bool

    existing_authority_allowed: bool

    temporal_guard_allowed: bool

    temporal_reasons: tuple[str, ...] = ()


class TemporalAutopilotAuthorityService:
    """
    Composition boundary between existing Autopilot authority
    and Temporal safety.

    Hard invariant:

        automatic execution
        =
        existing authority
        AND
        temporal safety guard

    Temporal Intelligence can veto autonomy.
    Temporal Intelligence can never create autonomy.

    No:
    - DB
    - persistence
    - execution
    - ranking
    - Brain
    - eligibility calculation
    - opt-in mutation
    - ML
    """

    def __init__(
        self,
        *,
        autopilot_authority: (
            AutopilotAuthorityService | None
        ) = None,
    ) -> None:
        self.autopilot_authority = (
            autopilot_authority
            or AutopilotAuthorityService()
        )

    def can_execute_automatically(
        self,
        *,
        execution_eligibility: (
            ExecutionEligibilityResult | None
        ),
        autopilot_enabled: bool,
        temporal_context: (
            TemporalAutopilotSafetyContext | None
        ),
    ) -> TemporalAutopilotAuthorityResult:
        existing_authority_allowed = (
            self.autopilot_authority
            .can_execute_automatically(
                execution_eligibility=(
                    execution_eligibility
                ),
                autopilot_enabled=autopilot_enabled,
            )
        )

        temporal_guard = (
            TemporalAutopilotGuardService.evaluate(
                context=temporal_context,
            )
        )

        return self._result(
            existing_authority_allowed=(
                existing_authority_allowed
            ),
            temporal_guard=temporal_guard,
        )

    def can_execute_stored_plan_automatically(
        self,
        *,
        plan: dict | None,
        autopilot_enabled: bool,
        temporal_context: (
            TemporalAutopilotSafetyContext | None
        ),
    ) -> TemporalAutopilotAuthorityResult:
        """
        Compose stored-plan Autopilot authority with
        Temporal Autopilot safety.

        Temporal Intelligence may veto existing authority.
        It can never grant authority on its own.
        """
        existing_authority_allowed = (
            self.autopilot_authority
            .can_execute_stored_plan_automatically(
                plan=plan,
                autopilot_enabled=autopilot_enabled,
            )
        )

        temporal_guard = (
            TemporalAutopilotGuardService.evaluate(
                context=temporal_context,
            )
        )

        return self._result(
            existing_authority_allowed=(
                existing_authority_allowed
            ),
            temporal_guard=temporal_guard,
        )

    @staticmethod
    def _result(
        *,
        existing_authority_allowed: bool,
        temporal_guard: TemporalAutopilotGuardResult,
    ) -> TemporalAutopilotAuthorityResult:
        return TemporalAutopilotAuthorityResult(
            allowed=(
                existing_authority_allowed
                and temporal_guard.allowed
            ),
            existing_authority_allowed=(
                existing_authority_allowed
            ),
            temporal_guard_allowed=(
                temporal_guard.allowed
            ),
            temporal_reasons=temporal_guard.reasons,
        )