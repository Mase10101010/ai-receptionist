from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
    CalibrationState,
)
from app.intelligence_decision.schemas import (
    RecommendationDecision,
    RecommendationDecisionLevel,
    RecommendationDecisionReason,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)
from app.intelligence_prediction.schemas import (
    PlanAcceptancePrediction,
    PredictionConfidence,
)


class IntelligenceDecisionService:
    def build_decision(
        self,
        *,
        restaurant_id: uuid.UUID,
        reservation_id: uuid.UUID | None,
        base_score: float,
        moved_reservations_count: int,
        total_seat_waste: int,
        prediction: PlanAcceptancePrediction,
        calibration: CalibrationMetrics | None,
        policy: RecommendationPolicy,
    ) -> RecommendationDecision:
        reasons: list[
            RecommendationDecisionReason
        ] = []

        level = (
            RecommendationDecisionLevel
            .REVIEW_RECOMMENDED
        )

        if (
            calibration is None
            or calibration.state
            == CalibrationState.INSUFFICIENT_DATA
        ):
            reasons.append(
                RecommendationDecisionReason(
                    code="calibration_not_mature",
                    description=(
                        "Alias does not yet have enough "
                        "evaluated predictions to treat this "
                        "recommendation as highly reliable."
                    ),
                )
            )

        if (
            prediction.acceptance_probability
            >= 0.80
        ):
            reasons.append(
                RecommendationDecisionReason(
                    code="high_acceptance_probability",
                    description=(
                        "The plan closely matches the "
                        "manager's observed seating preferences."
                    ),
                )
            )

        elif (
            prediction.acceptance_probability
            < 0.60
        ):
            reasons.append(
                RecommendationDecisionReason(
                    code="low_acceptance_probability",
                    description=(
                        "The plan has a relatively weak match "
                        "with the manager's observed decisions."
                    ),
                )
            )

        if moved_reservations_count == 0:
            reasons.append(
                RecommendationDecisionReason(
                    code="no_moves_required",
                    description=(
                        "The plan does not require moving "
                        "any existing reservation."
                    ),
                )
            )

        elif (
            policy.maximum_preferred_moves
            is not None
            and moved_reservations_count
            > policy.maximum_preferred_moves
        ):
            reasons.append(
                RecommendationDecisionReason(
                    code="above_preferred_move_limit",
                    description=(
                        "The plan requires more reservation "
                        "moves than the learned preference."
                    ),
                )
            )

        if total_seat_waste == 0:
            reasons.append(
                RecommendationDecisionReason(
                    code="exact_capacity_fit",
                    description=(
                        "The plan creates no unused seating "
                        "capacity."
                    ),
                )
            )

        if (
            policy.minimum_recommended_score
            is not None
            and base_score
            < policy.minimum_recommended_score
        ):
            reasons.append(
                RecommendationDecisionReason(
                    code="below_recommended_score",
                    description=(
                        "The technical score is below the "
                        "current learned recommendation "
                        "reference."
                    ),
                )
            )

        calibration_mature = (
            calibration is not None
            and calibration.state
            != CalibrationState.INSUFFICIENT_DATA
        )

        strong_conditions = (
            calibration_mature
            and prediction.confidence
            == PredictionConfidence.HIGH
            and prediction.acceptance_probability
            >= 0.85
            and (
                policy.minimum_recommended_score
                is None
                or base_score
                >= policy.minimum_recommended_score
            )
            and (
                policy.maximum_preferred_moves
                is None
                or moved_reservations_count
                <= policy.maximum_preferred_moves
            )
            and (
                policy.maximum_preferred_seat_waste
                is None
                or total_seat_waste
                <= policy.maximum_preferred_seat_waste
            )
        )

        recommended_conditions = (
            prediction.acceptance_probability
            >= 0.70
            and (
                policy.minimum_recommended_score
                is None
                or base_score
                >= policy.minimum_recommended_score
            )
            and (
                policy.maximum_preferred_moves
                is None
                or moved_reservations_count
                <= policy.maximum_preferred_moves
            )
        )

        if strong_conditions:
            level = (
                RecommendationDecisionLevel
                .STRONG_RECOMMENDATION
            )

        elif recommended_conditions:
            level = (
                RecommendationDecisionLevel
                .RECOMMENDED
            )

        summary = self._summary(
            level=level,
            automation_level=(
                policy.automation_level
            ),
        )

        return RecommendationDecision(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            level=level,
            confidence=prediction.confidence,
            summary=summary,
            reasons=reasons,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    @staticmethod
    def _summary(
        *,
        level: RecommendationDecisionLevel,
        automation_level: AutomationLevel,
    ) -> str:
        if (
            level
            == RecommendationDecisionLevel
            .STRONG_RECOMMENDATION
        ):
            return (
                "Alias considers this a strong "
                "recommendation based on the current "
                "evidence and learned preferences."
            )

        if (
            level
            == RecommendationDecisionLevel
            .RECOMMENDED
        ):
            if (
                automation_level
                == AutomationLevel.ADVISORY_ONLY
            ):
                return (
                    "Alias recommends this plan, but the "
                    "current evidence still calls for "
                    "explicit manager review."
                )

            return (
                "Alias recommends this plan based on the "
                "current learned preferences."
            )

        return (
            "Alias recommends manager review before "
            "accepting this plan."
        )