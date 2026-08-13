from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_decision.schemas import (
    RecommendationDecision,
    RecommendationDecisionLevel,
)
from app.intelligence_execution.schemas import (
    ExecutionEligibility,
)
from app.intelligence_execution.service import (
    IntelligenceExecutionEligibilityService,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)
from app.intelligence_prediction.schemas import (
    PredictionConfidence,
)


RESTAURANT_ID = uuid.uuid4()
RESERVATION_ID = uuid.uuid4()


def build_policy(
    automation_level: AutomationLevel,
) -> RecommendationPolicy:
    return RecommendationPolicy(
        restaurant_id=RESTAURANT_ID,
        move_penalty_weight=1.0,
        seat_waste_penalty_weight=1.0,
        score_weight=1.0,
        single_move_bonus=0.0,
        low_seat_waste_bonus=0.0,
        minimum_recommended_score=None,
        maximum_preferred_moves=None,
        maximum_preferred_seat_waste=None,
        automation_level=automation_level,
        rationale=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_decision(
    *,
    level: RecommendationDecisionLevel,
    confidence: PredictionConfidence,
) -> RecommendationDecision:
    return RecommendationDecision(
        restaurant_id=RESTAURANT_ID,
        reservation_id=RESERVATION_ID,
        level=level,
        confidence=confidence,
        summary="Test decision.",
        reasons=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def test_advisory_only_is_blocked():
    result = (
        IntelligenceExecutionEligibilityService()
        .evaluate(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            policy=build_policy(
                AutomationLevel.ADVISORY_ONLY,
            ),
            decision=build_decision(
                level=(
                    RecommendationDecisionLevel
                    .STRONG_RECOMMENDATION
                ),
                confidence=(
                    PredictionConfidence.HIGH
                ),
            ),
        )
    )

    assert (
        result.eligibility
        == ExecutionEligibility.BLOCKED
    )


def test_assisted_requires_manager_confirmation():
    result = (
        IntelligenceExecutionEligibilityService()
        .evaluate(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            policy=build_policy(
                AutomationLevel.ASSISTED,
            ),
            decision=build_decision(
                level=(
                    RecommendationDecisionLevel
                    .STRONG_RECOMMENDATION
                ),
                confidence=(
                    PredictionConfidence.HIGH
                ),
            ),
        )
    )

    assert (
        result.eligibility
        == ExecutionEligibility
        .MANAGER_CONFIRMATION_REQUIRED
    )


def test_automation_policy_still_requires_strong_decision():
    result = (
        IntelligenceExecutionEligibilityService()
        .evaluate(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            policy=build_policy(
                AutomationLevel
                .ELIGIBLE_FOR_AUTOMATION,
            ),
            decision=build_decision(
                level=(
                    RecommendationDecisionLevel
                    .RECOMMENDED
                ),
                confidence=(
                    PredictionConfidence.HIGH
                ),
            ),
        )
    )

    assert (
        result.eligibility
        == ExecutionEligibility
        .MANAGER_CONFIRMATION_REQUIRED
    )


def test_strong_high_confidence_can_be_eligible():
    result = (
        IntelligenceExecutionEligibilityService()
        .evaluate(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            policy=build_policy(
                AutomationLevel
                .ELIGIBLE_FOR_AUTOMATION,
            ),
            decision=build_decision(
                level=(
                    RecommendationDecisionLevel
                    .STRONG_RECOMMENDATION
                ),
                confidence=(
                    PredictionConfidence.HIGH
                ),
            ),
        )
    )

    assert (
        result.eligibility
        == ExecutionEligibility
        .ELIGIBLE_FOR_AUTOMATIC_EXECUTION
    )