"""Read-only spatial assessment of technical assignment candidates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from app.intelligence.types import CandidateAssignment
from app.services.spatial_intelligence.preference_evaluator import (
    SpatialPreference,
    SpatialPreferenceEvaluation,
)


@dataclass(frozen=True)
class SpatialCandidateAssessment:
    resource_id: str
    table_ids: tuple[str, ...]
    preference: SpatialPreference
    evaluable: bool
    separation: float | None


class SpatialCandidateAssessmentService:
    """Assess candidate geometry without changing technical scores."""

    @staticmethod
    def assess(
        *,
        candidates: Sequence[CandidateAssignment],
        evaluations: Sequence[SpatialPreferenceEvaluation],
        preference: SpatialPreference,
    ) -> list[SpatialCandidateAssessment]:
        by_table_id = {
            str(evaluation.table_id): evaluation
            for evaluation in evaluations
            if evaluation.preference == preference
        }

        results: list[SpatialCandidateAssessment] = []

        for candidate in candidates:
            distances: list[float] = []
            evaluable = bool(candidate.table_ids)

            for table_id in candidate.table_ids:
                evaluation = by_table_id.get(table_id)

                if (
                    evaluation is None
                    or not evaluation.evaluable
                    or evaluation.separation is None
                ):
                    evaluable = False
                    break

                distances.append(evaluation.separation)

            results.append(
                SpatialCandidateAssessment(
                    resource_id=candidate.resource_id,
                    table_ids=tuple(str(table_id) for table_id in candidate.table_ids),
                    preference=preference,
                    evaluable=evaluable,
                    separation=(
                        max(distances)
                        if evaluable and distances
                        else None
                    ),
                )
            )

        return results
