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

from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
    CalibrationState,
)


class RecommendationPolicyService:
    def build_policy(
        self,
        *,
        profile: AISuggestionBehaviourProfile,
        calibration: CalibrationMetrics | None = None,
    ) -> RecommendationPolicy:
        move_penalty_weight = 1.0
        seat_waste_penalty_weight = 1.0
        score_weight = 1.0

        move_direction = self._lower_is_preferred(
            accepted=profile.average_moves_accepted,
            dismissed=profile.average_moves_dismissed,
        )

        seat_waste_direction = (
            self._lower_is_preferred(
                accepted=(
                    profile
                    .average_seat_waste_accepted
                ),
                dismissed=(
                    profile
                    .average_seat_waste_dismissed
                ),
            )
        )

        score_direction = self._higher_is_preferred(
            accepted=profile.accepted_score_reference,
            dismissed=profile.dismissed_score_reference,
        )

        single_move_bonus = 0.0
        low_seat_waste_bonus = 0.0

        minimum_recommended_score = (
            self._minimum_score(
                profile,
            )
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

        move_penalty_weight = (
            self._dynamic_weight(
                base=move_penalty_weight,
                strength=(
                    profile.move_preference_strength
                ),
                direction=move_direction,
                upward_range=0.25,
                downward_range=0.15,
                minimum=0.70,
                maximum=1.60,
            )
        )

        seat_waste_penalty_weight = (
            self._dynamic_weight(
                base=seat_waste_penalty_weight,
                strength=(
                    profile
                    .seat_waste_preference_strength
                ),
                direction=seat_waste_direction,
                upward_range=0.30,
                downward_range=0.15,
                minimum=0.70,
                maximum=1.60,
            )
        )

        score_weight = (
            self._dynamic_weight(
                base=score_weight,
                strength=(
                    profile.score_preference_strength
                ),
                direction=score_direction,
                upward_range=0.40,
                downward_range=0.10,
                minimum=0.80,
                maximum=1.40,
            )
        )

        if (
            profile.average_seat_waste_accepted
            is not None
        ):
            maximum_preferred_seat_waste = max(
                0,
                round(
                    profile
                    .average_seat_waste_accepted
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
            self._automation_level(
                profile=profile,
                calibration=calibration,
            )
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
    def _lower_is_preferred(
        *,
        accepted: float | None,
        dismissed: float | None,
    ) -> int:
        if (
            accepted is None
            or dismissed is None
        ):
            return 0

        if accepted < dismissed:
            return 1

        if accepted > dismissed:
            return -1

        return 0

    @staticmethod
    def _higher_is_preferred(
        *,
        accepted: float | None,
        dismissed: float | None,
    ) -> int:
        if (
            accepted is None
            or dismissed is None
        ):
            return 0

        if accepted > dismissed:
            return 1

        if accepted < dismissed:
            return -1

        return 0

    @staticmethod
    def _dynamic_weight(
        *,
        base: float,
        strength: float,
        direction: int,
        upward_range: float,
        downward_range: float,
        minimum: float,
        maximum: float,
    ) -> float:
        if direction > 0:
            value = (
                base
                + (
                    strength
                    * upward_range
                )
            )

        elif direction < 0:
            value = (
                base
                - (
                    strength
                    * downward_range
                )
            )

        else:
            value = base

        value = max(
            minimum,
            min(
                maximum,
                value,
            ),
        )

        return round(
            value,
            4,
        )

    @staticmethod
    def _automation_level(
        *,
        profile: AISuggestionBehaviourProfile,
        calibration: CalibrationMetrics | None,
    ) -> AutomationLevel:
        if (
            profile.confidence
            == BehaviourConfidence.LOW
        ):
            return AutomationLevel.ADVISORY_ONLY

        if calibration is not None:
            if (
                calibration.state
                == CalibrationState.INSUFFICIENT_DATA
            ):
                return AutomationLevel.ADVISORY_ONLY

            if (
                profile.trust_level
                == ManagerTrustLevel.HIGH
                and profile.confidence
                == BehaviourConfidence.HIGH
                and calibration.state
                == CalibrationState.WELL_CALIBRATED
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