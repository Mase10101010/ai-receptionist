"""Conservative, read-only spatial preference decision policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.intelligence_temporal.candidate_ranking import TemporalRankedCandidate
from app.services.spatial_intelligence.candidate_assessment import (
    SpatialCandidateAssessment,
)


@dataclass(frozen=True)
class SpatialPreferenceDecision:
    selected_index: int
    applied: bool
    reason: str


class SpatialPreferencePolicy:
    """Select spatially better candidates only at equivalent temporal cost."""

    @staticmethod
    def choose(
        *,
        ranked_candidates: Sequence[TemporalRankedCandidate],
        assessments: Sequence[SpatialCandidateAssessment],
    ) -> SpatialPreferenceDecision:
        if not ranked_candidates:
            return SpatialPreferenceDecision(
                selected_index=0,
                applied=False,
                reason="no_temporal_candidates",
            )

        baseline = ranked_candidates[0]
        baseline_score = baseline.ranking.effective_score
        baseline_loss = baseline.ranking.lost_future_available_slots
        baseline_loss_ratio = baseline.ranking.marginal_capacity_loss_ratio

        assessment_by_key = {
            assessment.table_ids: assessment
            for assessment in assessments
        }

        def spatial_distance(index: int) -> float | None:
            candidate = ranked_candidates[index].evaluation.candidate
            key = tuple(str(table_id) for table_id in candidate.table_ids)
            assessment = assessment_by_key.get(key)

            if (
                assessment is None
                or not assessment.evaluable
                or assessment.separation is None
            ):
                return None

            return assessment.separation

        baseline_distance = spatial_distance(0)

        if baseline_distance is None:
            return SpatialPreferenceDecision(
                selected_index=0,
                applied=False,
                reason="baseline_geometry_unavailable",
            )

        best_index = 0
        best_distance = baseline_distance

        for index in range(1, len(ranked_candidates)):
            candidate = ranked_candidates[index]

            if candidate.ranking.effective_score != baseline_score:
                continue

            if candidate.ranking.lost_future_available_slots > baseline_loss:
                continue
            if candidate.ranking.marginal_capacity_loss_ratio > baseline_loss_ratio:
                continue

            distance = spatial_distance(index)

            if distance is not None and distance < best_distance:
                best_index = index
                best_distance = distance

        return SpatialPreferenceDecision(
            selected_index=best_index,
            applied=best_index != 0,
            reason=(
                "equivalent_temporal_cost_spatial_improvement"
                if best_index != 0
                else "temporal_recommendation_preserved"
            ),
        )
