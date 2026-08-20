from __future__ import annotations

from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    BehaviourConfidence,
    ManagerTrustLevel,
)
from app.intelligence_automation_path.schemas import (
    AutomationPath,
    AutomationPathItem,
)
from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
    CalibrationState,
)
from app.intelligence_policy.schemas import (
    AutomationLevel,
    RecommendationPolicy,
)


class IntelligenceAutomationPathService:
    def build(
        self,
        *,
        profile: AISuggestionBehaviourProfile,
        policy: RecommendationPolicy,
        calibration: CalibrationMetrics,
    ) -> AutomationPath:
        current_level = policy.automation_level

        requirements: list[
            AutomationPathItem
        ] = []

        if (
            current_level
            == AutomationLevel.ADVISORY_ONLY
        ):
            next_level = AutomationLevel.ASSISTED

            requirements.extend(
                [
                    AutomationPathItem(
                        code="behaviour_confidence_above_low",
                        description=(
                            "Behaviour confidence must rise "
                            "above the low level."
                        ),
                        satisfied=(
                            profile.confidence
                            != BehaviourConfidence.LOW
                        ),
                    ),
                    AutomationPathItem(
                        code="calibration_data_sufficient",
                        description=(
                            "Alias needs enough evaluated "
                            "predictions to move beyond the "
                            "insufficient-data calibration state."
                        ),
                        satisfied=(
                            calibration.state
                            != CalibrationState
                            .INSUFFICIENT_DATA
                        ),
                    ),
                ]
            )

        elif (
            current_level
            == AutomationLevel.ASSISTED
        ):
            next_level = (
                AutomationLevel
                .ELIGIBLE_FOR_AUTOMATION
            )

            requirements.extend(
                [
                    AutomationPathItem(
                        code="manager_trust_high",
                        description=(
                            "Manager trust must reach the "
                            "high level."
                        ),
                        satisfied=(
                            profile.trust_level
                            == ManagerTrustLevel.HIGH
                        ),
                    ),
                    AutomationPathItem(
                        code="behaviour_confidence_high",
                        description=(
                            "Behaviour confidence must reach "
                            "the high level."
                        ),
                        satisfied=(
                            profile.confidence
                            == BehaviourConfidence.HIGH
                        ),
                    ),
                    AutomationPathItem(
                        code="calibration_well_calibrated",
                        description=(
                            "Prediction calibration must be "
                            "well calibrated."
                        ),
                        satisfied=(
                            calibration.state
                            == CalibrationState
                            .WELL_CALIBRATED
                        ),
                    ),
                ]
            )

        else:
            next_level = None

            requirements.extend(
                [
                    AutomationPathItem(
                        code="automation_eligibility_reached",
                        description=(
                            "The restaurant has reached the "
                            "current policy requirements for "
                            "automation eligibility."
                        ),
                        satisfied=True,
                    ),
                ]
            )

        return AutomationPath(
            restaurant_id=profile.restaurant_id,
            current_level=current_level,
            next_level=next_level,
            requirements=requirements,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )