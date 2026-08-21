from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    BehaviourConfidence,
    ManagerTrustLevel,
    PlanPreference,
)
from app.intelligence_policy.service import (
    RecommendationPolicyService,
)


RESTAURANT_ID = uuid.uuid4()


def build_profile(
    *,
    average_moves_accepted: float | None = 1.0,
    average_moves_dismissed: float | None = None,
    average_seat_waste_accepted: float | None = 0.0,
    average_seat_waste_dismissed: float | None = None,
    accepted_score_reference: float | None = 175.0,
    dismissed_score_reference: float | None = None,
    move_preference_strength: float = 0.0,
    seat_waste_preference_strength: float = 0.0,
    score_preference_strength: float = 0.0,
) -> AISuggestionBehaviourProfile:
    return AISuggestionBehaviourProfile(
        restaurant_id=RESTAURANT_ID,
        trust_level=(
            ManagerTrustLevel.DEVELOPING
        ),
        preferred_plan=(
            PlanPreference.FLEXIBLE
        ),
        accepted_score_reference=(
            accepted_score_reference
        ),
        dismissed_score_reference=(
            dismissed_score_reference
        ),
        average_moves_accepted=(
            average_moves_accepted
        ),
        average_moves_dismissed=(
            average_moves_dismissed
        ),
        average_seat_waste_accepted=(
            average_seat_waste_accepted
        ),
        average_seat_waste_dismissed=(
            average_seat_waste_dismissed
        ),
        move_preference_strength=(
            move_preference_strength
        ),
        seat_waste_preference_strength=(
            seat_waste_preference_strength
        ),
        score_preference_strength=(
            score_preference_strength
        ),
        total_suggestions_observed=20,
        total_manager_decisions=12,
        acceptance_rate=0.60,
        confidence=(
            BehaviourConfidence.MEDIUM
        ),
        insights=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_policy(
    profile: AISuggestionBehaviourProfile,
):
    return (
        RecommendationPolicyService()
        .build_policy(
            profile=profile,
        )
    )


def test_move_penalty_increases_when_accepted_plans_use_fewer_moves():
    policy = build_policy(
        build_profile(
            average_moves_accepted=1.0,
            average_moves_dismissed=3.0,
            move_preference_strength=0.6,
        )
    )

    assert (
        policy.move_penalty_weight
        > 1.0
    )


def test_move_penalty_decreases_when_accepted_plans_use_more_moves():
    policy = build_policy(
        build_profile(
            average_moves_accepted=3.0,
            average_moves_dismissed=1.0,
            move_preference_strength=0.6,
        )
    )

    assert (
        policy.move_penalty_weight
        < 1.0
    )


def test_seat_waste_penalty_increases_when_accepted_plans_waste_less():
    policy = build_policy(
        build_profile(
            average_seat_waste_accepted=0.0,
            average_seat_waste_dismissed=3.0,
            seat_waste_preference_strength=0.6,
        )
    )

    assert (
        policy.seat_waste_penalty_weight
        > 1.0
    )


def test_seat_waste_penalty_decreases_when_accepted_plans_waste_more():
    policy = build_policy(
        build_profile(
            average_seat_waste_accepted=3.0,
            average_seat_waste_dismissed=0.0,
            seat_waste_preference_strength=0.6,
        )
    )

    assert (
        policy.seat_waste_penalty_weight
        < 1.0
    )


def test_score_weight_increases_when_accepted_scores_are_higher():
    policy = build_policy(
        build_profile(
            accepted_score_reference=180.0,
            dismissed_score_reference=150.0,
            score_preference_strength=0.5,
        )
    )

    assert (
        policy.score_weight
        > 1.0
    )


def test_score_weight_decreases_when_accepted_scores_are_lower():
    policy = build_policy(
        build_profile(
            accepted_score_reference=150.0,
            dismissed_score_reference=180.0,
            score_preference_strength=0.5,
        )
    )

    assert (
        policy.score_weight
        < 1.0
    )


def test_weights_remain_neutral_without_comparative_evidence():
    policy = build_policy(
        build_profile(
            average_moves_dismissed=None,
            average_seat_waste_dismissed=None,
            dismissed_score_reference=None,
            move_preference_strength=0.0,
            seat_waste_preference_strength=0.0,
            score_preference_strength=0.0,
        )
    )

    assert (
        policy.move_penalty_weight
        == 1.0
    )

    assert (
        policy.seat_waste_penalty_weight
        == 1.0
    )

    assert (
        policy.score_weight
        == 1.0
    )