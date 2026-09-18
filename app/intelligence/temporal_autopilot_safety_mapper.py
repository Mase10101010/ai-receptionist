from __future__ import annotations

from app.intelligence.schemas import (
    IntelligenceTemporalAutopilotSafetyContext,
)
from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotSafetyContext,
)


class IntelligenceTemporalAutopilotSafetyMapper:
    """
    Maps Temporal Autopilot safety evidence into the
    Intelligence API boundary.

    Invariants:
    - no policy
    - no safety decision
    - no execution authority
    - no DB
    - no persistence
    """

    @classmethod
    def map(
        cls,
        *,
        context: TemporalAutopilotSafetyContext | None,
    ) -> IntelligenceTemporalAutopilotSafetyContext | None:
        if context is None:
            return None

        return IntelligenceTemporalAutopilotSafetyContext(
            calibration_state=(
                context.calibration_state.value
            ),
            expected_turn_confidence=(
                context.expected_turn_confidence.value
            ),
            marginal_capacity_loss_ratio=(
                context.marginal_capacity_loss_ratio
            ),
            lost_future_available_slots=(
                context.lost_future_available_slots
            ),
        )