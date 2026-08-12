from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
    CalibrationState,
)
from app.intelligence_decision.schemas import (
    RecommendationDecisionLevel,
)
from app.intelligence_decision.service import (
    IntelligenceDecisionService,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)
from app.intelligence_prediction.schemas import (
    PlanAcceptancePrediction,
    PredictionConfidence,
)


RESTAURANT_ID = uuid.uuid4()
RESERVATION_ID = uuid.uuid4()


def build_policy(
    *,
    automation_level: AutomationLevel = (
        AutomationLevel.ADVISORY_ONLY
    ),
) -> RecommendationPolicy:
    return RecommendationPolicy(
        restaurant_id=RESTAURANT_ID,
        move_penalty_weight=1.35,
        seat_waste_penalty_weight=1.0,
        score_weight=1.0,
        single_move_bonus=12.0,
        low_seat_waste_bonus=0.0,
        minimum_recommended_score=150.0,
        maximum_preferred_moves=1,
        maximum_preferred_seat_waste=1,
        automation_level=automation_level,
        rationale=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_prediction(
    *,
    probability: float,
    confidence: PredictionConfidence,
) -> PlanAcceptancePrediction:
    return PlanAcceptancePrediction(
        restaurant_id=RESTAURANT_ID,
        reservation_id=RESERVATION_ID,
        acceptance_probability=probability,
        confidence=confidence,
        explanation=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_calibration(
    *,
    state: CalibrationState,
    predictions_evaluated: int = 20,
) -> CalibrationMetrics:
    return CalibrationMetrics(
        restaurant_id=RESTAURANT_ID,
        predictions_evaluated=(
            predictions_evaluated
        ),
        correct_predictions=15,
        prediction_accuracy=0.75,
        average_absolute_error=0.15,
        brier_score=0.08,
        average_predicted_probability=0.75,
        actual_acceptance_rate=0.72,
        calibration_gap=0.03,
        state=state,
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def test_review_recommended_when_prediction_is_weak():
    decision = (
        IntelligenceDecisionService()
        .build_decision(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            base_score=90.0,
            moved_reservations_count=0,
            total_seat_waste=0,
            prediction=build_prediction(
                probability=0.51,
                confidence=(
                    PredictionConfidence.LOW
                ),
            ),
            calibration=build_calibration(
                state=(
                    CalibrationState
                    .INSUFFICIENT_DATA
                ),
                predictions_evaluated=3,
            ),
            policy=build_policy(),
        )
    )

    assert (
        decision.level
        == RecommendationDecisionLevel
        .REVIEW_RECOMMENDED
    )


def test_recommended_when_plan_is_good():
    decision = (
        IntelligenceDecisionService()
        .build_decision(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            base_score=170.0,
            moved_reservations_count=1,
            total_seat_waste=0,
            prediction=build_prediction(
                probability=0.78,
                confidence=(
                    PredictionConfidence.MEDIUM
                ),
            ),
            calibration=build_calibration(
                state=(
                    CalibrationState
                    .WELL_CALIBRATED
                ),
            ),
            policy=build_policy(
                automation_level=(
                    AutomationLevel.ASSISTED
                ),
            ),
        )
    )

    assert (
        decision.level
        == RecommendationDecisionLevel
        .RECOMMENDED
    )


def test_strong_recommendation_requires_mature_evidence():
    decision = (
        IntelligenceDecisionService()
        .build_decision(
            restaurant_id=RESTAURANT_ID,
            reservation_id=RESERVATION_ID,
            base_score=180.0,
            moved_reservations_count=1,
            total_seat_waste=0,
            prediction=build_prediction(
                probability=0.90,
                confidence=(
                    PredictionConfidence.HIGH
                ),
            ),
            calibration=build_calibration(
                state=(
                    CalibrationState
                    .WELL_CALIBRATED
                ),
            ),
            policy=build_policy(
                automation_level=(
                    AutomationLevel
                    .ELIGIBLE_FOR_AUTOMATION
                ),
            ),
        )
    )

    assert (
        decision.level
        == RecommendationDecisionLevel
        .STRONG_RECOMMENDATION
    )