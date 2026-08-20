from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_automation_path.service import (
    IntelligenceAutomationPathService,
)
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


RESTAURANT_ID = uuid.uuid4()


def build_profile(
    *,
    confidence: BehaviourConfidence,
    trust_level: ManagerTrustLevel,
) -> AISuggestionBehaviourProfile:
    return AISuggestionBehaviourProfile(
        restaurant_id=RESTAURANT_ID,
        trust_level=trust_level,
        preferred_plan=PlanPreference.SINGLE_MOVE,
        accepted_score_reference=180.0,
        average_moves_accepted=1.0,
        average_seat_waste_accepted=0.0,
        total_suggestions_observed=20,
        total_manager_decisions=10,
        confidence=confidence,
        insights=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_policy(
    level: AutomationLevel,
) -> RecommendationPolicy:
    return RecommendationPolicy(
        restaurant_id=RESTAURANT_ID,
        move_penalty_weight=1.0,
        seat_waste_penalty_weight=1.0,
        score_weight=1.0,
        single_move_bonus=0.0,
        low_seat_waste_bonus=0.0,
        minimum_recommended_score=170.0,
        maximum_preferred_moves=1,
        maximum_preferred_seat_waste=0,
        automation_level=level,
        rationale=[],
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def build_calibration(
    state: CalibrationState,
) -> CalibrationMetrics:
    return CalibrationMetrics(
        restaurant_id=RESTAURANT_ID,
        predictions_evaluated=20,
        correct_predictions=16,
        prediction_accuracy=0.8,
        average_absolute_error=0.1,
        brier_score=0.05,
        average_predicted_probability=0.75,
        actual_acceptance_rate=0.75,
        calibration_gap=0.0,
        state=state,
        generated_at=datetime.now(
            timezone.utc,
        ),
    )


def test_advisory_path_points_to_assisted():
    result = (
        IntelligenceAutomationPathService()
        .build(
            profile=build_profile(
                confidence=BehaviourConfidence.LOW,
                trust_level=ManagerTrustLevel.LOW,
            ),
            policy=build_policy(
                AutomationLevel.ADVISORY_ONLY,
            ),
            calibration=build_calibration(
                CalibrationState.INSUFFICIENT_DATA,
            ),
        )
    )

    assert (
        result.current_level
        == AutomationLevel.ADVISORY_ONLY
    )
    assert (
        result.next_level
        == AutomationLevel.ASSISTED
    )

    assert all(
        not item.satisfied
        for item in result.requirements
    )


def test_assisted_path_points_to_automation():
    result = (
        IntelligenceAutomationPathService()
        .build(
            profile=build_profile(
                confidence=BehaviourConfidence.MEDIUM,
                trust_level=ManagerTrustLevel.DEVELOPING,
            ),
            policy=build_policy(
                AutomationLevel.ASSISTED,
            ),
            calibration=build_calibration(
                CalibrationState.OVERCONFIDENT,
            ),
        )
    )

    assert (
        result.current_level
        == AutomationLevel.ASSISTED
    )
    assert (
        result.next_level
        == AutomationLevel
        .ELIGIBLE_FOR_AUTOMATION
    )


def test_eligible_has_no_next_level():
    result = (
        IntelligenceAutomationPathService()
        .build(
            profile=build_profile(
                confidence=BehaviourConfidence.HIGH,
                trust_level=ManagerTrustLevel.HIGH,
            ),
            policy=build_policy(
                AutomationLevel
                .ELIGIBLE_FOR_AUTOMATION,
            ),
            calibration=build_calibration(
                CalibrationState.WELL_CALIBRATED,
            ),
        )
    )

    assert (
        result.current_level
        == AutomationLevel
        .ELIGIBLE_FOR_AUTOMATION
    )
    assert result.next_level is None
    assert all(
        item.satisfied
        for item in result.requirements
    )