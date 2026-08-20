from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    BehaviourConfidence,
    PlanPreference,
)
from app.intelligence_policy.schemas import (
    RecommendationPolicy,
)
from app.intelligence_prediction.schemas import (
    PlanAcceptancePrediction,
    PredictionConfidence,
)

from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
)


class IntelligencePredictionService:
    def predict_plan_acceptance(
        self,
        *,
        restaurant_id: uuid.UUID,
        reservation_id: uuid.UUID | None,
        base_score: float,
        personalized_score: float,
        moved_reservations_count: int,
        total_seat_waste: int,
        behaviour: AISuggestionBehaviourProfile,
        policy: RecommendationPolicy,
        calibration: CalibrationMetrics | None = None,
    ) -> PlanAcceptancePrediction:
        probability = self._base_probability(
            behaviour=behaviour,
        )

        explanation: list[str] = []

        if (
            moved_reservations_count == 1
            and behaviour.preferred_plan
            == PlanPreference.SINGLE_MOVE
        ):
            probability += 0.15
            explanation.append(
                "The plan matches the manager's learned "
                "preference for single-reservation moves."
            )

        elif (
            policy.maximum_preferred_moves
            is not None
            and moved_reservations_count
            > policy.maximum_preferred_moves
        ):
            probability -= 0.20
            explanation.append(
                "The plan requires more reservation moves "
                "than the current learned preference."
            )

        if total_seat_waste == 0:
            probability += 0.10
            explanation.append(
                "The plan creates no unused seating capacity."
            )

        elif (
            policy.maximum_preferred_seat_waste
            is not None
            and total_seat_waste
            > policy.maximum_preferred_seat_waste
        ):
            probability -= 0.10
            explanation.append(
                "The plan creates more unused seating "
                "capacity than is currently preferred."
            )

        if (
            policy.minimum_recommended_score
            is not None
        ):
            if (
                base_score
                >= policy.minimum_recommended_score
            ):
                probability += 0.10
                explanation.append(
                    "The technical score is above the "
                    "current learned recommendation reference."
                )
            else:
                probability -= 0.05
                explanation.append(
                    "The technical score is below the "
                    "current learned recommendation reference."
                )

        personalization_delta = (
            personalized_score
            - base_score
        )

        if personalization_delta > 0.01:
            probability += 0.10
            explanation.append(
                "The restaurant's learned preferences "
                "increase this plan's ranking."
            )

        elif personalization_delta < -0.01:
            probability -= 0.10
            explanation.append(
                "The restaurant's learned preferences "
                "reduce this plan's ranking."
            )

        if (
            calibration is not None
            and calibration.predictions_evaluated > 0
        ):
            evidence_weight = (
                calibration.predictions_evaluated
                / (
                    calibration.predictions_evaluated
                    + 20
                )
            )

            calibration_correction = (
                calibration.calibration_gap
                * evidence_weight
            )

            calibration_correction = max(
                -0.25,
                min(
                    0.25,
                    calibration_correction,
                ),
            )

            probability -= calibration_correction

            if calibration_correction > 0.005:
                explanation.append(
                    "Alias reduced this probability because "
                    "recent predictions have been more "
                    "confident than actual manager acceptance."
                )

            elif calibration_correction < -0.005:
                explanation.append(
                    "Alias increased this probability because "
                    "recent predictions have been more "
                    "cautious than actual manager acceptance."
                )

        probability = max(
            0.0,
            min(
                1.0,
                probability,
            ),
        )

        probability = round(
            probability,
            4,
        )

        return PlanAcceptancePrediction(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            acceptance_probability=probability,
            confidence=self._prediction_confidence(
                behaviour=behaviour,
            ),
            explanation=explanation,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    @staticmethod
    def _base_probability(
        *,
        behaviour: AISuggestionBehaviourProfile,
    ) -> float:
        decisions = (
            behaviour.total_manager_decisions
        )

        if decisions <= 0:
            return 0.50

        observed_rate = (
            behaviour.acceptance_rate
        )

        prior_weight = 5.0
        prior_probability = 0.50

        probability = (
            (
                observed_rate * decisions
            )
            + (
                prior_probability
                * prior_weight
            )
        ) / (
            decisions
            + prior_weight
        )

        return probability

    @staticmethod
    def _prediction_confidence(
        *,
        behaviour: AISuggestionBehaviourProfile,
    ) -> PredictionConfidence:
        if (
            behaviour.confidence
            == BehaviourConfidence.HIGH
        ):
            return PredictionConfidence.HIGH

        if (
            behaviour.confidence
            == BehaviourConfidence.MEDIUM
        ):
            return PredictionConfidence.MEDIUM

        return PredictionConfidence.LOW