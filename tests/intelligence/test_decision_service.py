from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

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


def _build_prediction(
    *,
    restaurant_id: uuid.UUID,
) -> PlanAcceptancePrediction:
    return PlanAcceptancePrediction(
        restaurant_id=restaurant_id,
        reservation_id=uuid.uuid4(),
        acceptance_probability=0.90,
        confidence=PredictionConfidence.HIGH,
        explanation=[],
        generated_at=datetime.now(timezone.utc),
    )


def _build_calibration(
    *,
    restaurant_id: uuid.UUID,
    state: CalibrationState,
) -> CalibrationMetrics:
    return CalibrationMetrics(
        restaurant_id=restaurant_id,
        predictions_evaluated=20,
        correct_predictions=18,
        prediction_accuracy=0.90,
        average_absolute_error=0.10,
        brier_score=0.05,
        average_predicted_probability=0.80,
        actual_acceptance_rate=0.80,
        calibration_gap=0.0,
        state=state,
        generated_at=datetime.now(timezone.utc),
    )


def _build_policy(
    *,
    restaurant_id: uuid.UUID,
) -> RecommendationPolicy:
    return RecommendationPolicy(
        restaurant_id=restaurant_id,
        move_penalty_weight=1.0,
        seat_waste_penalty_weight=1.0,
        score_weight=1.0,
        single_move_bonus=0.0,
        low_seat_waste_bonus=0.0,
        minimum_recommended_score=80.0,
        maximum_preferred_moves=1,
        maximum_preferred_seat_waste=2,
        automation_level=AutomationLevel.ASSISTED,
        rationale=[],
        generated_at=datetime.now(timezone.utc),
    )


def _build_decision(
    *,
    calibration_state: CalibrationState,
):
    restaurant_id = uuid.uuid4()
    reservation_id = uuid.uuid4()

    service = IntelligenceDecisionService()

    return service.build_decision(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        base_score=90.0,
        moved_reservations_count=1,
        total_seat_waste=1,
        prediction=_build_prediction(
            restaurant_id=restaurant_id,
        ),
        calibration=_build_calibration(
            restaurant_id=restaurant_id,
            state=calibration_state,
        ),
        policy=_build_policy(
            restaurant_id=restaurant_id,
        ),
    )


def test_well_calibrated_can_produce_strong_recommendation():
    decision = _build_decision(
        calibration_state=(
            CalibrationState.WELL_CALIBRATED
        ),
    )

    assert (
        decision.level
        == RecommendationDecisionLevel.STRONG_RECOMMENDATION
    )


@pytest.mark.parametrize(
    "calibration_state",
    [
        CalibrationState.OVERCONFIDENT,
        CalibrationState.UNDERCONFIDENT,
        CalibrationState.INSUFFICIENT_DATA,
    ],
)
def test_non_well_calibrated_does_not_produce_strong_recommendation(
    calibration_state: CalibrationState,
):
    decision = _build_decision(
        calibration_state=calibration_state,
    )

    assert (
        decision.level
        != RecommendationDecisionLevel.STRONG_RECOMMENDATION
    )