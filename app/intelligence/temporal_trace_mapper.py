from __future__ import annotations

from app.intelligence_temporal.ranking_decision_trace import (
    TemporalRankingCandidateTrace,
    TemporalRankingDecisionTrace,
)

from .schemas import (
    IntelligenceTemporalCandidateTrace,
    IntelligenceTemporalDecisionTrace,
)


class IntelligenceTemporalTraceMapper:
    """
    Maps Temporal ranking audit truth to the Intelligence
    production response boundary.

    Invariants:
    - no ranking
    - no score calculation
    - no DB
    - no persistence
    - no mutation
    - no Brain
    - no Autopilot
    """

    @classmethod
    def map(
        cls,
        *,
        trace: TemporalRankingDecisionTrace,
    ) -> IntelligenceTemporalDecisionTrace:
        return IntelligenceTemporalDecisionTrace(
            technical_winner=cls._candidate(trace.technical_winner),
            temporal_winner=cls._candidate(trace.temporal_winner),
            recommendation_changed=trace.recommendation_changed,
        )

    @staticmethod
    def _candidate(
        trace: TemporalRankingCandidateTrace,
    ) -> IntelligenceTemporalCandidateTrace:
        return IntelligenceTemporalCandidateTrace(
            table_ids=trace.table_ids,
            technical_score=trace.technical_score,
            effective_score=trace.effective_score,
            marginal_capacity_loss_ratio=(
                trace.marginal_capacity_loss_ratio
            ),
            lost_future_available_slots=(
                trace.lost_future_available_slots
            ),
        )