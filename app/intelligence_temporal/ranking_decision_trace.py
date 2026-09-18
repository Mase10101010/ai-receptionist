from __future__ import annotations

from pydantic import BaseModel

from .candidate_ranking import TemporalRankedCandidate


class TemporalRankingCandidateTrace(BaseModel):
    """
    Immutable view of candidate truth used for ranking audit.
    """

    table_ids: tuple[str, ...]
    technical_score: float
    effective_score: float
    marginal_capacity_loss_ratio: float
    lost_future_available_slots: int


class TemporalRankingDecisionTrace(BaseModel):
    """
    Comparison between the original technical recommendation
    and the final temporal recommendation.
    """

    technical_winner: TemporalRankingCandidateTrace
    temporal_winner: TemporalRankingCandidateTrace
    recommendation_changed: bool


class TemporalRankingDecisionTraceService:
    """
    Builds a deterministic decision trace from already-ranked truth.

    Invariants:
    - no ranking
    - no score calculation
    - no optimizer calls
    - no DB
    - no persistence
    - no mutation
    - no Brain
    - no Autopilot
    - no ML
    """

    @classmethod
    def build(
        cls,
        *,
        technical_winner: TemporalRankedCandidate,
        temporal_winner: TemporalRankedCandidate,
    ) -> TemporalRankingDecisionTrace:
        technical_trace = cls._candidate_trace(
            candidate=technical_winner,
        )
        temporal_trace = cls._candidate_trace(
            candidate=temporal_winner,
        )

        return TemporalRankingDecisionTrace(
            technical_winner=technical_trace,
            temporal_winner=temporal_trace,
            recommendation_changed=(
                technical_trace.table_ids
                != temporal_trace.table_ids
            ),
        )

    @staticmethod
    def _candidate_trace(
        *,
        candidate: TemporalRankedCandidate,
    ) -> TemporalRankingCandidateTrace:
        assignment = candidate.evaluation.candidate
        ranking = candidate.ranking

        return TemporalRankingCandidateTrace(
            table_ids=tuple(
                str(table_id)
                for table_id in assignment.table_ids
            ),
            technical_score=assignment.score,
            effective_score=ranking.effective_score,
            marginal_capacity_loss_ratio=(
                ranking.marginal_capacity_loss_ratio
            ),
            lost_future_available_slots=(
                ranking.lost_future_available_slots
            ),
        )