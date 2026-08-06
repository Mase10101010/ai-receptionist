from __future__ import annotations

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


class RecommendationPolicyService:
    def build_policy(
        self,
        *,
        profile: AISuggestionBehaviourProfile,
    ) -> RecommendationPolicy:
        move_penalty_weight = 1.0
        seat_waste_penalty_weight = 1.0
        score_weight = 1.0

        single_move_bonus = 0.0
        low_seat_waste_bonus = 0.0

        minimum_recommended_score = (
            self._minimum_score(profile)
        )

        maximum_preferred_moves: int | None = None
        maximum_preferred_seat_waste: int | None = None

        rationale: list[str] = []

        if (
            profile.preferred_plan
            == PlanPreference.SINGLE_MOVE
        ):
            move_penalty_weight = 1.35
            single_move_bonus = 12.0
            maximum_preferred_moves = 1

            rationale.append(
                "Accepted plans currently favour "
                "single-reservation moves."
            )

        elif (
            profile.preferred_plan
            == PlanPreference.MULTI_MOVE
        ):
            move_penalty_weight = 0.75
            maximum_preferred_moves = 3

            rationale.append(
                "The manager appears comfortable with "
                "plans involving multiple moves."
            )

        elif (
            profile.preferred_plan
            == PlanPreference.LOW_SEAT_WASTE
        ):
            seat_waste_penalty_weight = 1.5
            low_seat_waste_bonus = 10.0
            maximum_preferred_seat_waste = 1

            rationale.append(
                "Accepted plans currently favour minimal "
                "unused seating capacity."
            )

        elif (
            profile.preferred_plan
            == PlanPreference.FLEXIBLE
        ):
            rationale.append(
                "No dominant plan structure has emerged, "
                "so balanced ranking weights are used."
            )

        else:
            rationale.append(
                "There is not enough evidence to personalize "
                "plan structure aggressively."
            )

        if (
            profile.average_seat_waste_accepted
            is not None
        ):
            maximum_preferred_seat_waste = max(
                0,
                round(
                    profile.average_seat_waste_accepted
                ),
            )

        if (
            profile.average_moves_accepted
            is not None
        ):
            maximum_preferred_moves = max(
                1,
                round(
                    profile.average_moves_accepted
                ),
            )

        automation_level = (
            self._automation_level(profile)
        )

        rationale.append(
            self._automation_rationale(
                automation_level,
            )
        )

        if minimum_recommended_score is not None:
            rationale.append(
                "Plans below the learned score reference "
                "should remain subject to explicit manager review."
            )

        return RecommendationPolicy(
            restaurant_id=profile.restaurant_id,
            move_penalty_weight=(
                move_penalty_weight
            ),
            seat_waste_penalty_weight=(
                seat_waste_penalty_weight
            ),
            score_weight=score_weight,
            single_move_bonus=single_move_bonus,
            low_seat_waste_bonus=(
                low_seat_waste_bonus
            ),
            minimum_recommended_score=(
                minimum_recommended_score
            ),
            maximum_preferred_moves=(
                maximum_preferred_moves
            ),
            maximum_preferred_seat_waste=(
                maximum_preferred_seat_waste
            ),
            automation_level=automation_level,
            rationale=rationale,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    @staticmethod
    def _minimum_score(
        profile: AISuggestionBehaviourProfile,
    ) -> float | None:
        reference = (
            profile.accepted_score_reference
        )

        if reference is None:
            return None

        if (
            profile.confidence
            == BehaviourConfidence.LOW
        ):
            return round(
                reference * 0.9,
                2,
            )

        if (
            profile.confidence
            == BehaviourConfidence.MEDIUM
        ):
            return round(
                reference * 0.95,
                2,
            )

        return round(
            reference,
            2,
        )

    @staticmethod
    def _automation_level(
        profile: AISuggestionBehaviourProfile,
    ) -> AutomationLevel:
        if (
            profile.confidence
            == BehaviourConfidence.LOW
        ):
            return AutomationLevel.ADVISORY_ONLY

        if (
            profile.trust_level
            == ManagerTrustLevel.HIGH
            and profile.confidence
            == BehaviourConfidence.HIGH
        ):
            return (
                AutomationLevel
                .ELIGIBLE_FOR_AUTOMATION
            )

        return AutomationLevel.ASSISTED

    @staticmethod
    def _automation_rationale(
        level: AutomationLevel,
    ) -> str:
        descriptions = {
            AutomationLevel.ADVISORY_ONLY: (
                "Alias should continue presenting plans "
                "for explicit manager review."
            ),
            AutomationLevel.ASSISTED: (
                "Alias may prioritize and preselect plans, "
                "but manager confirmation is still required."
            ),
            AutomationLevel.ELIGIBLE_FOR_AUTOMATION: (
                "The observed confidence and manager trust "
                "may support future opt-in automation."
            ),
        }

        return descriptions[level]