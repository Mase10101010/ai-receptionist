from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_decision.schemas import (
    RecommendationDecision,
    RecommendationDecisionLevel,
)
from app.intelligence_execution.schemas import (
    ExecutionEligibility,
    ExecutionEligibilityReason,
    ExecutionEligibilityResult,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)
from app.intelligence_prediction.schemas import (
    PredictionConfidence,
)


class IntelligenceExecutionEligibilityService:
    def evaluate(
        self,
        *,
        restaurant_id: uuid.UUID,
        reservation_id: uuid.UUID | None,
        policy: RecommendationPolicy,
        decision: RecommendationDecision,
    ) -> ExecutionEligibilityResult:
        reasons: list[
            ExecutionEligibilityReason
        ] = []

        if (
            policy.automation_level
            == AutomationLevel.ADVISORY_ONLY
        ):
            reasons.append(
                ExecutionEligibilityReason(
                    code="policy_advisory_only",
                    description=(
                        "The restaurant is currently in "
                        "advisory-only mode."
                    ),
                )
            )

            return ExecutionEligibilityResult(
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                eligibility=(
                    ExecutionEligibility.BLOCKED
                ),
                reasons=reasons,
                generated_at=datetime.now(
                    timezone.utc,
                ),
            )

        if (
            policy.automation_level
            == AutomationLevel.ASSISTED
        ):
            reasons.append(
                ExecutionEligibilityReason(
                    code="manager_confirmation_required",
                    description=(
                        "The restaurant is in assisted mode, "
                        "so manager confirmation is required."
                    ),
                )
            )

            return ExecutionEligibilityResult(
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                eligibility=(
                    ExecutionEligibility
                    .MANAGER_CONFIRMATION_REQUIRED
                ),
                reasons=reasons,
                generated_at=datetime.now(
                    timezone.utc,
                ),
            )

        if (
            decision.level
            != RecommendationDecisionLevel
            .STRONG_RECOMMENDATION
        ):
            reasons.append(
                ExecutionEligibilityReason(
                    code="decision_not_strong_enough",
                    description=(
                        "The current recommendation is not "
                        "strong enough for automatic execution."
                    ),
                )
            )

            return ExecutionEligibilityResult(
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                eligibility=(
                    ExecutionEligibility
                    .MANAGER_CONFIRMATION_REQUIRED
                ),
                reasons=reasons,
                generated_at=datetime.now(
                    timezone.utc,
                ),
            )

        if (
            decision.confidence
            != PredictionConfidence.HIGH
        ):
            reasons.append(
                ExecutionEligibilityReason(
                    code="prediction_confidence_not_high",
                    description=(
                        "Prediction confidence is not high "
                        "enough for automatic execution."
                    ),
                )
            )

            return ExecutionEligibilityResult(
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                eligibility=(
                    ExecutionEligibility
                    .MANAGER_CONFIRMATION_REQUIRED
                ),
                reasons=reasons,
                generated_at=datetime.now(
                    timezone.utc,
                ),
            )

        reasons.append(
            ExecutionEligibilityReason(
                code="automatic_execution_eligible",
                description=(
                    "The restaurant policy and current "
                    "recommendation meet the requirements "
                    "for future automatic execution."
                ),
            )
        )

        return ExecutionEligibilityResult(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            eligibility=(
                ExecutionEligibility
                .ELIGIBLE_FOR_AUTOMATIC_EXECUTION
            ),
            reasons=reasons,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )