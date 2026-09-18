from __future__ import annotations

from pydantic import BaseModel

from .candidate_temporal_evaluator import (
    TemporalCandidateEvaluation,
)
from .temporal_ranking import (
    TemporalRankingPolicy,
    TemporalRankingScore,
)


class TemporalRankedCandidate(BaseModel):
    evaluation: TemporalCandidateEvaluation
    ranking: TemporalRankingScore


class TemporalCandidateRankingResult(BaseModel):
    ranked: list[TemporalRankedCandidate]


class TemporalCandidateRankingService:
    """
    Pure temporal ordering over already-evaluated candidates.

    Invariants:
    - no optimizer calls
    - no DB
    - no persistence
    - no candidate generation
    - no score mutation
    - no Brain
    - no Autopilot
    - no ML
    """

    @classmethod
    def rank(
        cls,
        *,
        evaluations: list[TemporalCandidateEvaluation],
    ) -> TemporalCandidateRankingResult:
        ranked = [
            TemporalRankedCandidate(
                evaluation=evaluation,
                ranking=TemporalRankingPolicy.score(
                    cost=(
                        evaluation
                        .counterfactual
                        .cost
                    ),
                ),
            )
            for evaluation in evaluations
        ]

        ranked.sort(
            key=cls._sort_key,
        )

        return TemporalCandidateRankingResult(
            ranked=ranked,
        )

    @staticmethod
    def _sort_key(
        item: TemporalRankedCandidate,
    ) -> tuple:
        candidate = item.evaluation.candidate

        return (
            -item.ranking.effective_score,
            item.ranking.marginal_capacity_loss_ratio,
            item.ranking.lost_future_available_slots,
            candidate.seat_waste,
            candidate.fragmentation_minutes,
            len(candidate.table_ids),
            tuple(
                str(table_id)
                for table_id in candidate.table_ids
            ),
        )