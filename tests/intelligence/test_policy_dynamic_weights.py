from __future__ import annotations

import pytest

from app.intelligence_policy.service import (
    RecommendationPolicyService,
)


def test_lower_is_preferred_detects_lower_accepted_value():
    direction = (
        RecommendationPolicyService
        ._lower_is_preferred(
            accepted=1.0,
            dismissed=3.0,
        )
    )

    assert direction == 1


def test_lower_is_preferred_detects_higher_accepted_value():
    direction = (
        RecommendationPolicyService
        ._lower_is_preferred(
            accepted=3.0,
            dismissed=1.0,
        )
    )

    assert direction == -1


def test_lower_is_preferred_is_neutral_without_data():
    direction = (
        RecommendationPolicyService
        ._lower_is_preferred(
            accepted=None,
            dismissed=1.0,
        )
    )

    assert direction == 0


def test_higher_is_preferred_detects_higher_accepted_value():
    direction = (
        RecommendationPolicyService
        ._higher_is_preferred(
            accepted=180.0,
            dismissed=150.0,
        )
    )

    assert direction == 1


def test_higher_is_preferred_detects_lower_accepted_value():
    direction = (
        RecommendationPolicyService
        ._higher_is_preferred(
            accepted=140.0,
            dismissed=170.0,
        )
    )

    assert direction == -1


def test_dynamic_weight_increases_with_positive_direction():
    value = (
        RecommendationPolicyService
        ._dynamic_weight(
            base=1.0,
            strength=0.5,
            direction=1,
            upward_range=0.4,
            downward_range=0.1,
            minimum=0.8,
            maximum=1.4,
        )
    )

    assert value == pytest.approx(
        1.2,
    )


def test_dynamic_weight_decreases_with_negative_direction():
    value = (
        RecommendationPolicyService
        ._dynamic_weight(
            base=1.0,
            strength=0.5,
            direction=-1,
            upward_range=0.4,
            downward_range=0.2,
            minimum=0.7,
            maximum=1.4,
        )
    )

    assert value == pytest.approx(
        0.9,
    )


def test_dynamic_weight_stays_neutral_without_direction():
    value = (
        RecommendationPolicyService
        ._dynamic_weight(
            base=1.0,
            strength=1.0,
            direction=0,
            upward_range=0.4,
            downward_range=0.2,
            minimum=0.7,
            maximum=1.4,
        )
    )

    assert value == 1.0


def test_dynamic_weight_respects_maximum():
    value = (
        RecommendationPolicyService
        ._dynamic_weight(
            base=1.35,
            strength=1.0,
            direction=1,
            upward_range=0.5,
            downward_range=0.1,
            minimum=0.7,
            maximum=1.6,
        )
    )

    assert value == 1.6


def test_dynamic_weight_respects_minimum():
    value = (
        RecommendationPolicyService
        ._dynamic_weight(
            base=0.75,
            strength=1.0,
            direction=-1,
            upward_range=0.2,
            downward_range=0.5,
            minimum=0.7,
            maximum=1.6,
        )
    )

    assert value == 0.7