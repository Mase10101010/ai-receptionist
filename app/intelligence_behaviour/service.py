from __future__ import annotations

from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    BehaviourConfidence,
    BehaviourInsight,
    ManagerTrustLevel,
    PlanPreference,
)
from app.intelligence_features.schemas import (
    AISuggestionFeatures,
)


class IntelligenceBehaviourService:
    def build_ai_suggestion_profile(
        self,
        *,
        features: AISuggestionFeatures,
    ) -> AISuggestionBehaviourProfile:
        total_manager_decisions = (
            features.suggestions_accepted
            + features.suggestions_dismissed
        )

        confidence = self._confidence_for_samples(
            features.suggestions_created,
        )

        trust_level = self._calculate_trust_level(
            created=features.suggestions_created,
            accepted=features.suggestions_accepted,
            acceptance_rate=features.acceptance_rate,
        )

        preferred_plan = self._calculate_plan_preference(
            average_moves_accepted=(
                features.average_moves_accepted
            ),
            average_seat_waste_accepted=(
                features.average_seat_waste_accepted
            ),
            accepted_count=(
                features.suggestions_accepted
            ),
        )

        insights = self._build_insights(
            features=features,
            trust_level=trust_level,
            preferred_plan=preferred_plan,
            confidence=confidence,
            total_manager_decisions=(
                total_manager_decisions
            ),
        )

        evidence_weight = (
            self._preference_evidence_weight(
                accepted=features.suggestions_accepted,
                dismissed=features.suggestions_dismissed,
            )
        )

        move_preference_strength = (
            self._preference_strength(
                accepted_value=(
                    features.average_moves_accepted
                ),
                dismissed_value=(
                    features.average_moves_dismissed
                ),
                evidence_weight=evidence_weight,
            )
        )

        seat_waste_preference_strength = (
            self._preference_strength(
                accepted_value=(
                    features
                    .average_seat_waste_accepted
                ),
                dismissed_value=(
                    features
                    .average_seat_waste_dismissed
                ),
                evidence_weight=evidence_weight,
            )
        )

        score_preference_strength = (
            self._preference_strength(
                accepted_value=(
                    features.average_accepted_score
                ),
                dismissed_value=(
                    features.average_dismissed_score
                ),
                evidence_weight=evidence_weight,
            )
        )

        return AISuggestionBehaviourProfile(
            restaurant_id=features.restaurant_id,
            trust_level=trust_level,
            preferred_plan=preferred_plan,
            accepted_score_reference=(
                features.average_accepted_score
            ),
            average_moves_accepted=(
                features.average_moves_accepted
            ),
            average_seat_waste_accepted=(
                features.average_seat_waste_accepted
            ),
            dismissed_score_reference=(
                features.average_dismissed_score
            ),
            average_moves_dismissed=(
                features.average_moves_dismissed
            ),
            average_seat_waste_dismissed=(
                features.average_seat_waste_dismissed
            ),

            move_preference_strength=(
                move_preference_strength
            ),
            seat_waste_preference_strength=(
                seat_waste_preference_strength
            ),
            score_preference_strength=(
                score_preference_strength
            ),
            total_suggestions_observed=(
                features.suggestions_created
            ),
            total_manager_decisions=(
                total_manager_decisions
            ),
            acceptance_rate=(
                features.acceptance_rate
            ),
            confidence=confidence,
            insights=insights,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    @staticmethod
    def _confidence_for_samples(
        sample_count: int,
    ) -> BehaviourConfidence:
        if sample_count >= 20:
            return BehaviourConfidence.HIGH

        if sample_count >= 5:
            return BehaviourConfidence.MEDIUM

        return BehaviourConfidence.LOW

    @staticmethod
    def _calculate_trust_level(
        *,
        created: int,
        accepted: int,
        acceptance_rate: float,
    ) -> ManagerTrustLevel:
        if created < 3:
            return ManagerTrustLevel.UNKNOWN

        if accepted == 0:
            return ManagerTrustLevel.LOW

        if acceptance_rate >= 0.7:
            return ManagerTrustLevel.HIGH

        if acceptance_rate >= 0.3:
            return ManagerTrustLevel.DEVELOPING

        return ManagerTrustLevel.LOW

    @staticmethod
    def _calculate_plan_preference(
        *,
        average_moves_accepted: float | None,
        average_seat_waste_accepted: float | None,
        accepted_count: int,
    ) -> PlanPreference:
        if accepted_count == 0:
            return PlanPreference.UNKNOWN

        if (
            average_moves_accepted is not None
            and average_moves_accepted <= 1.25
        ):
            return PlanPreference.SINGLE_MOVE

        if (
            average_seat_waste_accepted is not None
            and average_seat_waste_accepted <= 1.0
        ):
            return PlanPreference.LOW_SEAT_WASTE

        if (
            average_moves_accepted is not None
            and average_moves_accepted >= 2.0
        ):
            return PlanPreference.MULTI_MOVE

        return PlanPreference.FLEXIBLE

    def _build_insights(
        self,
        *,
        features: AISuggestionFeatures,
        trust_level: ManagerTrustLevel,
        preferred_plan: PlanPreference,
        confidence: BehaviourConfidence,
        total_manager_decisions: int,
    ) -> list[BehaviourInsight]:
        insights: list[BehaviourInsight] = []

        insights.append(
            BehaviourInsight(
                code="manager_trust",
                title="Manager trust level",
                description=(
                    self._trust_description(
                        trust_level,
                    )
                ),
                confidence=confidence,
                evidence_count=(
                    total_manager_decisions
                ),
                value=trust_level.value,
            )
        )

        if features.average_accepted_score is not None:
            insights.append(
                BehaviourInsight(
                    code="accepted_score_reference",
                    title="Accepted score reference",
                    description=(
                        "Accepted seating plans currently "
                        "have an average score of "
                        f"{features.average_accepted_score:.2f}."
                    ),
                    confidence=confidence,
                    evidence_count=(
                        features.suggestions_accepted
                    ),
                    value=round(
                        features.average_accepted_score,
                        2,
                    ),
                )
            )

        if preferred_plan != PlanPreference.UNKNOWN:
            insights.append(
                BehaviourInsight(
                    code="preferred_plan_structure",
                    title="Preferred plan structure",
                    description=(
                        self._preference_description(
                            preferred_plan,
                        )
                    ),
                    confidence=confidence,
                    evidence_count=(
                        features.suggestions_accepted
                    ),
                    value=preferred_plan.value,
                )
            )

        if features.suggestions_expired > 0:
            insights.append(
                BehaviourInsight(
                    code="expired_suggestions",
                    title="Suggestions becoming obsolete",
                    description=(
                        f"{features.suggestions_expired} "
                        "suggestion(s) became obsolete before "
                        "a manager decision was recorded."
                    ),
                    confidence=confidence,
                    evidence_count=(
                        features.suggestions_expired
                    ),
                    value=(
                        features.suggestions_expired
                    ),
                )
            )

        if features.read_rate < 0.5:
            insights.append(
                BehaviourInsight(
                    code="low_review_rate",
                    title="Low suggestion review rate",
                    description=(
                        "Less than half of the generated "
                        "suggestions have been reviewed."
                    ),
                    confidence=confidence,
                    evidence_count=(
                        features.suggestions_created
                    ),
                    value=features.read_rate,
                )
            )

        return insights

    @staticmethod
    def _trust_description(
        trust_level: ManagerTrustLevel,
    ) -> str:
        descriptions = {
            ManagerTrustLevel.UNKNOWN: (
                "There is not enough evidence yet to "
                "estimate manager trust reliably."
            ),
            ManagerTrustLevel.LOW: (
                "The manager currently accepts few of "
                "Alias's seating suggestions."
            ),
            ManagerTrustLevel.DEVELOPING: (
                "The manager is selectively adopting "
                "Alias's seating suggestions."
            ),
            ManagerTrustLevel.HIGH: (
                "The manager frequently accepts Alias's "
                "seating suggestions."
            ),
        }

        return descriptions[trust_level]

    @staticmethod
    def _preference_description(
        preference: PlanPreference,
    ) -> str:
        descriptions = {
            PlanPreference.UNKNOWN: (
                "No plan preference is available yet."
            ),
            PlanPreference.SINGLE_MOVE: (
                "Accepted plans usually require only one "
                "existing reservation to be moved."
            ),
            PlanPreference.MULTI_MOVE: (
                "The manager appears comfortable accepting "
                "plans involving multiple reservation moves."
            ),
            PlanPreference.LOW_SEAT_WASTE: (
                "The manager tends to accept plans that "
                "minimize unused seats."
            ),
            PlanPreference.FLEXIBLE: (
                "No dominant seating-plan structure has "
                "emerged from accepted suggestions."
            ),
        }

        return descriptions[preference]

    @staticmethod
    def _preference_evidence_weight(
        *,
        accepted: int,
        dismissed: int,
    ) -> float:
        comparable_samples = min(
            accepted,
            dismissed,
        )

        return min(
            comparable_samples / 5.0,
            1.0,
        )


    @staticmethod
    def _preference_strength(
        *,
        accepted_value: float | None,
        dismissed_value: float | None,
        evidence_weight: float,
    ) -> float:
        if (
            accepted_value is None
            or dismissed_value is None
        ):
            return 0.0

        scale = max(
            abs(accepted_value),
            abs(dismissed_value),
            1.0,
        )

        separation = (
            abs(
                accepted_value
                - dismissed_value
            )
            / scale
        )

        strength = (
            min(
                separation,
                1.0,
            )
            * evidence_weight
        )

        return round(
            strength,
            4,
        )