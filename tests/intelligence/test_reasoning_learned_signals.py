from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    BehaviourConfidence,
    ManagerTrustLevel,
    PlanPreference,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)
from app.intelligence_reasoning.schemas import (
    LearnedSignalDirection,
    LearnedSignalStrength,
)
from app.intelligence_reasoning.service import (
    IntelligenceReasoningService,
)


RESTAURANT_ID = uuid.uuid4()
RESERVATION_ID = uuid.uuid4()


def build_behaviour(
    *,
    average_moves_accepted: float | None = 1.0,
    average_moves_dismissed: float | None = 1.0,
    average_seat_waste_accepted: float | None = 0.0,
    average_seat_waste_dismissed: float | None = 0.0,
    accepted_score_reference: float | None = 174.0,
    dismissed_score_reference: float | None = 176.0,
    move_preference_strength: float = 0.0,
    seat_waste_preference_strength: float = 0.0,
    score_preference_strength: float = 0.01,
) -> AISuggestionBehaviourProfile:
    return AISuggestionBehaviourProfile(
        restaurant_id=RESTAURANT_ID,
        trust_level=ManagerTrustLevel.DEVELOPING,
        preferred_plan=PlanPreference.SINGLE_MOVE,
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
        acceptance_rate=0.5,
        confidence=BehaviourConfidence.HIGH,
        insights=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_policy() -> RecommendationPolicy:
    return RecommendationPolicy(
        restaurant_id=RESTAURANT_ID,
        move_penalty_weight=1.35,
        seat_waste_penalty_weight=1.0,
        score_weight=1.0,
        single_move_bonus=12.0,
        low_seat_waste_bonus=0.0,
        minimum_recommended_score=170.0,
        maximum_preferred_moves=1,
        maximum_preferred_seat_waste=0,
        automation_level=AutomationLevel.ASSISTED,
        rationale=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_reasoning(
    behaviour: AISuggestionBehaviourProfile,
):
    return (
        IntelligenceReasoningService()
        .build_recommendation_reasoning(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            base_score=172.75,
            personalized_score=173.0,
            moved_reservations_count=1,
            total_seat_waste=0,
            behaviour=behaviour,
            policy=build_policy(),
        )
    )


def signal_by_code(
    reasoning,
    code: str,
):
    return next(
        signal
        for signal in reasoning.learned_signals
        if signal.code == code
    )


def test_equal_move_values_are_neutral():
    reasoning = build_reasoning(
        build_behaviour(
            average_moves_accepted=1.0,
            average_moves_dismissed=1.0,
            move_preference_strength=0.0,
        )
    )

    signal = signal_by_code(
        reasoning,
        "move_structure",
    )

    assert (
        signal.strength
        == LearnedSignalStrength.NONE
    )

    assert (
        signal.direction
        == LearnedSignalDirection.NEUTRAL
    )


def test_lower_moves_in_accepted_plans_are_preferred():
    reasoning = build_reasoning(
        build_behaviour(
            average_moves_accepted=1.0,
            average_moves_dismissed=3.0,
            move_preference_strength=0.5,
        )
    )

    signal = signal_by_code(
        reasoning,
        "move_structure",
    )

    assert (
        signal.strength
        == LearnedSignalStrength.HIGH
    )

    assert (
        signal.direction
        == LearnedSignalDirection.PREFERRED
    )


def test_higher_moves_in_accepted_plans_are_avoided():
    reasoning = build_reasoning(
        build_behaviour(
            average_moves_accepted=3.0,
            average_moves_dismissed=1.0,
            move_preference_strength=0.3,
        )
    )

    signal = signal_by_code(
        reasoning,
        "move_structure",
    )

    assert (
        signal.strength
        == LearnedSignalStrength.MEDIUM
    )

    assert (
        signal.direction
        == LearnedSignalDirection.AVOIDED
    )


def test_equal_seat_waste_values_are_neutral():
    reasoning = build_reasoning(
        build_behaviour(
            average_seat_waste_accepted=0.0,
            average_seat_waste_dismissed=0.0,
            seat_waste_preference_strength=0.0,
        )
    )

    signal = signal_by_code(
        reasoning,
        "seat_waste",
    )

    assert (
        signal.direction
        == LearnedSignalDirection.NEUTRAL
    )

    assert (
        signal.strength
        == LearnedSignalStrength.NONE
    )


def test_higher_score_in_accepted_plans_is_preferred():
    reasoning = build_reasoning(
        build_behaviour(
            accepted_score_reference=180.0,
            dismissed_score_reference=150.0,
            score_preference_strength=0.25,
        )
    )

    signal = signal_by_code(
        reasoning,
        "technical_score",
    )

    assert (
        signal.direction
        == LearnedSignalDirection.PREFERRED
    )

    assert (
        signal.strength
        == LearnedSignalStrength.MEDIUM
    )


def test_higher_score_in_dismissed_plans_is_avoided():
    reasoning = build_reasoning(
        build_behaviour(
            accepted_score_reference=174.0,
            dismissed_score_reference=176.0,
            score_preference_strength=0.01,
        )
    )

    signal = signal_by_code(
        reasoning,
        "technical_score",
    )

    assert (
        signal.direction
        == LearnedSignalDirection.AVOIDED
    )

    assert (
        signal.strength
        == LearnedSignalStrength.LOW
    )


def test_missing_comparable_values_returns_no_signal_strength():
    reasoning = build_reasoning(
        build_behaviour(
            average_moves_accepted=1.0,
            average_moves_dismissed=None,
            move_preference_strength=0.0,
        )
    )

    signal = signal_by_code(
        reasoning,
        "move_structure",
    )

    assert (
        signal.strength
        == LearnedSignalStrength.NONE
    )

    assert (
        signal.direction
        == LearnedSignalDirection.NEUTRAL
    )