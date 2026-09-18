from __future__ import annotations

from pydantic import BaseModel

from .candidate_cost import TemporalCandidateCost


class TemporalRankingScore(BaseModel):
    base_score: float
    temporal_penalty: float
    effective_score: float

    marginal_capacity_loss_ratio: float
    lost_future_available_slots: int


class TemporalRankingPolicy:
    """
    Deterministic ranking policy for temporal optimization.

    V1 intentionally keeps technical score untouched and derives
    a separate effective score.

    Invariants:
    - pure
    - no DB
    - no optimizer calls
    - no persistence
    - no Brain
    - no Autopilot
    - no ML
    """

    TEMPORAL_PENALTY_WEIGHT = 25.0

    @classmethod
    def score(
        cls,
        *,
        cost: TemporalCandidateCost,
    ) -> TemporalRankingScore:
        penalty = (
            cost.marginal_capacity_loss_ratio
            * cls.TEMPORAL_PENALTY_WEIGHT
        )

        effective_score = (
            cost.base_score
            - penalty
        )

        return TemporalRankingScore(
            base_score=cost.base_score,
            temporal_penalty=penalty,
            effective_score=effective_score,
            marginal_capacity_loss_ratio=(
                cost.marginal_capacity_loss_ratio
            ),
            lost_future_available_slots=(
                cost.lost_future_available_slots
            ),
        )