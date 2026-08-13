from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
    IntelligenceReoptimizationPlanResponse,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)
from app.intelligence_decision.schemas import (
    RecommendationDecision,
    RecommendationDecisionLevel,
)
from app.intelligence_prediction.schemas import (
    PredictionConfidence,
)


RESTAURANT_ID = uuid.uuid4()


def build_plan(
    *,
    level: RecommendationDecisionLevel | None,
    personalized_score: float,
    base_score: float,
) -> IntelligenceReoptimizationPlanResponse:
    decision = None

    if level is not None:
        decision = RecommendationDecision(
            restaurant_id=RESTAURANT_ID,
            reservation_id=None,
            level=level,
            confidence=PredictionConfidence.MEDIUM,
            summary="Test decision.",
            reasons=[],
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    return IntelligenceReoptimizationPlanResponse(
        new_reservation_assignment=(
            IntelligenceAssignmentResponse(
                table_ids=[uuid.uuid4()],
                table_numbers=["1"],
                start_at=datetime.now(
                    timezone.utc,
                ),
                end_at=datetime.now(
                    timezone.utc,
                ),
                capacity=4,
                score=base_score,
                seat_waste=0,
                fragmentation_minutes=0,
                explanation="Test assignment.",
            )
        ),
        moves=[],
        score=base_score,
        base_score=base_score,
        personalized_score=personalized_score,
        personalization_applied=True,
        personalization_reasons=[],
        reasoning=None,
        acceptance_prediction=None,
        decision=decision,
        total_seat_waste=0,
        moved_reservations_count=0,
        explanation="Test plan.",
    )


def ranking_key(
    plan: IntelligenceReoptimizationPlanResponse,
):
    return (
        IntelligenceOptimizationService
        ._decision_rank(plan),
        plan.personalized_score,
        plan.base_score,
    )


def test_recommended_beats_review_recommended():
    review_plan = build_plan(
        level=(
            RecommendationDecisionLevel
            .REVIEW_RECOMMENDED
        ),
        personalized_score=200.0,
        base_score=190.0,
    )

    recommended_plan = build_plan(
        level=(
            RecommendationDecisionLevel
            .RECOMMENDED
        ),
        personalized_score=180.0,
        base_score=170.0,
    )

    ranked = sorted(
        [
            review_plan,
            recommended_plan,
        ],
        key=ranking_key,
        reverse=True,
    )

    assert ranked[0] is recommended_plan


def test_strong_recommendation_beats_recommended():
    recommended_plan = build_plan(
        level=(
            RecommendationDecisionLevel
            .RECOMMENDED
        ),
        personalized_score=210.0,
        base_score=200.0,
    )

    strong_plan = build_plan(
        level=(
            RecommendationDecisionLevel
            .STRONG_RECOMMENDATION
        ),
        personalized_score=180.0,
        base_score=170.0,
    )

    ranked = sorted(
        [
            recommended_plan,
            strong_plan,
        ],
        key=ranking_key,
        reverse=True,
    )

    assert ranked[0] is strong_plan


def test_personalized_score_breaks_same_level_tie():
    lower_score_plan = build_plan(
        level=(
            RecommendationDecisionLevel
            .RECOMMENDED
        ),
        personalized_score=180.0,
        base_score=175.0,
    )

    higher_score_plan = build_plan(
        level=(
            RecommendationDecisionLevel
            .RECOMMENDED
        ),
        personalized_score=190.0,
        base_score=170.0,
    )

    ranked = sorted(
        [
            lower_score_plan,
            higher_score_plan,
        ],
        key=ranking_key,
        reverse=True,
    )

    assert ranked[0] is higher_score_plan