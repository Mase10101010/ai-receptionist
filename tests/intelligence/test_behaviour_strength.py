from __future__ import annotations

import pytest

from app.intelligence_behaviour.service import (
    IntelligenceBehaviourService,
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