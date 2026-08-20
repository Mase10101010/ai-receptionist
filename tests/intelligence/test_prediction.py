from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    BehaviourConfidence,
    ManagerTrustLevel,
    PlanPreference,
)
from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
    CalibrationState,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)
from app.intelligence_prediction.service import (
    IntelligencePredictionService,
)


RESTAURANT_ID = uuid.uuid4()
RESERVATION_ID = uuid.uuid4()


def build_behaviour(
    *,
    acceptance_rate: float,
    total_manager_decisions: int,
    confidence: BehaviourConfidence = (
        BehaviourConfidence.MEDIUM
    ),
) -> AISuggestionBehaviourProfile:
    return AISuggestionBehaviourProfile(
        restaurant_id=RESTAURANT_ID,
        trust_level=ManagerTrustLevel.DEVELOPING,
        preferred_plan=PlanPreference.FLEXIBLE,
        accepted_score_reference=None,
        average_moves_accepted=None,
        average_seat_waste_accepted=None,
        total_suggestions_observed=(
            total_manager_decisions
        ),
        total_manager_decisions=(
            total_manager_decisions
        ),
        acceptance_rate=acceptance_rate,
        confidence=confidence,
        insights=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_policy() -> RecommendationPolicy:
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
        automation_level=(
            AutomationLevel.ASSISTED
        ),
        rationale=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_calibration(
    *,
    predictions_evaluated: int,
    calibration_gap: float,
) -> CalibrationMetrics:
    return CalibrationMetrics(
        restaurant_id=RESTAURANT_ID,
        predictions_evaluated=(
            predictions_evaluated
        ),
        correct_predictions=0,
        prediction_accuracy=0.0,
        average_absolute_error=0.0,
        brier_score=0.0,
        average_predicted_probability=0.0,
        actual_acceptance_rate=0.0,
        calibration_gap=calibration_gap,
        state=(
            CalibrationState.OVERCONFIDENT
            if calibration_gap > 0.10
            else CalibrationState.WELL_CALIBRATED
        ),
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def predict(
    *,
    behaviour: AISuggestionBehaviourProfile,
    calibration: CalibrationMetrics | None = None,
):
    return (
        IntelligencePredictionService()
        .predict_plan_acceptance(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            base_score=100.0,
            personalized_score=100.0,
            moved_reservations_count=0,
            total_seat_waste=1,
            behaviour=behaviour,
            policy=build_policy(),
            calibration=calibration,
        )
    )


def test_no_manager_decisions_starts_at_neutral_probability():
    result = predict(
        behaviour=build_behaviour(
            acceptance_rate=0.0,
            total_manager_decisions=0,
        ),
    )

    assert result.acceptance_probability == 0.5


def test_low_acceptance_rate_reduces_base_probability():
    result = predict(
        behaviour=build_behaviour(
            acceptance_rate=0.20,
            total_manager_decisions=10,
        ),
    )

    assert (
        result.acceptance_probability
        < 0.5
    )

    assert (
        result.acceptance_probability
        == 0.3
    )


def test_high_acceptance_rate_increases_base_probability():
    result = predict(
        behaviour=build_behaviour(
            acceptance_rate=0.80,
            total_manager_decisions=10,
        ),
    )

    assert (
        result.acceptance_probability
        > 0.5
    )

    assert (
        result.acceptance_probability
        == 0.7
    )


def test_prior_smoothing_keeps_small_samples_conservative():
    result = predict(
        behaviour=build_behaviour(
            acceptance_rate=1.0,
            total_manager_decisions=1,
        ),
    )

    assert (
        result.acceptance_probability
        == 0.5833
    )


def test_overconfidence_calibration_reduces_probability():
    without_calibration = predict(
        behaviour=build_behaviour(
            acceptance_rate=0.80,
            total_manager_decisions=10,
        ),
    )

    with_calibration = predict(
        behaviour=build_behaviour(
            acceptance_rate=0.80,
            total_manager_decisions=10,
        ),
        calibration=build_calibration(
            predictions_evaluated=10,
            calibration_gap=0.30,
        ),
    )

    assert (
        with_calibration.acceptance_probability
        < without_calibration.acceptance_probability
    )

    assert (
        with_calibration.acceptance_probability
        == 0.6
    )

    assert any(
        "reduced this probability"
        in item
        for item in with_calibration.explanation
    )