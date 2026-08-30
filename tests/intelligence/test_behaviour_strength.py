from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.intelligence_behaviour.service import (
    IntelligenceBehaviourService,
)
from app.intelligence_features.schemas import (
    AISuggestionFeatures,
)


def test_preference_evidence_weight_requires_both_sides():
    weight = (
        IntelligenceBehaviourService
        ._preference_evidence_weight(
            accepted=5,
            dismissed=0,
        )
    )

    assert weight == 0.0


def test_preference_evidence_weight_grows_with_comparable_samples():
    weight = (
        IntelligenceBehaviourService
        ._preference_evidence_weight(
            accepted=5,
            dismissed=2,
        )
    )

    assert weight == pytest.approx(0.4)


def test_preference_evidence_weight_caps_at_one():
    weight = (
        IntelligenceBehaviourService
        ._preference_evidence_weight(
            accepted=10,
            dismissed=8,
        )
    )

    assert weight == 1.0


def test_preference_strength_is_zero_without_comparable_values():
    strength = (
        IntelligenceBehaviourService
        ._preference_strength(
            accepted_value=1.0,
            dismissed_value=None,
            evidence_weight=1.0,
        )
    )

    assert strength == 0.0


def test_preference_strength_is_zero_when_values_match():
    strength = (
        IntelligenceBehaviourService
        ._preference_strength(
            accepted_value=2.0,
            dismissed_value=2.0,
            evidence_weight=1.0,
        )
    )

    assert strength == 0.0


def test_preference_strength_detects_strong_separation():
    strength = (
        IntelligenceBehaviourService
        ._preference_strength(
            accepted_value=1.0,
            dismissed_value=3.0,
            evidence_weight=1.0,
        )
    )

    assert strength == pytest.approx(
        0.6667,
    )


def test_preference_strength_is_dampened_by_limited_evidence():
    strength = (
        IntelligenceBehaviourService
        ._preference_strength(
            accepted_value=1.0,
            dismissed_value=3.0,
            evidence_weight=0.4,
        )
    )

    assert strength == pytest.approx(
        0.2667,
    )


def test_preference_strength_handles_score_scale():
    strength = (
        IntelligenceBehaviourService
        ._preference_strength(
            accepted_value=180.0,
            dismissed_value=150.0,
            evidence_weight=1.0,
        )
    )

    assert strength == pytest.approx(
        0.1667,
    )


def test_preference_strength_never_exceeds_one():
    strength = (
        IntelligenceBehaviourService
        ._preference_strength(
            accepted_value=0.0,
            dismissed_value=100.0,
            evidence_weight=1.0,
        )
    )

    assert strength == 1.0


def test_move_complexity_strength_requires_comparable_evidence():
    features = AISuggestionFeatures(
        restaurant_id=uuid.uuid4(),
        suggestions_created=1,
        suggestions_accepted=1,
        suggestions_dismissed=0,
        average_move_complexity_accepted=1.0,
        move_complexity_accepted_samples=1,
        average_move_complexity_dismissed=None,
        move_complexity_dismissed_samples=0,
        generated_at=datetime.now(
            timezone.utc,
        ),
    )

    profile = (
        IntelligenceBehaviourService()
        .build_ai_suggestion_profile(
            features=features,
        )
    )

    assert (
        profile.move_complexity_preference_strength
        == 0.0
    )


def test_move_complexity_strength_uses_dedicated_samples():
    features = AISuggestionFeatures(
        restaurant_id=uuid.uuid4(),
        suggestions_created=20,
        suggestions_accepted=10,
        suggestions_dismissed=10,
        average_move_complexity_accepted=1.0,
        move_complexity_accepted_samples=2,
        average_move_complexity_dismissed=2.0,
        move_complexity_dismissed_samples=2,
        generated_at=datetime.now(
            timezone.utc,
        ),
    )

    profile = (
        IntelligenceBehaviourService()
        .build_ai_suggestion_profile(
            features=features,
        )
    )

    assert (
        profile.move_complexity_preference_strength
        == pytest.approx(0.2)
    )