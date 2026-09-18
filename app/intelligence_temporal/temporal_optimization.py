from __future__ import annotations

from pydantic import BaseModel

from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    OptimizationResult,
    ScoredAssignment,
    TableCombination,
)

from .calibration_state import (
    TemporalCalibrationAssessment,
)
from .candidate_ranking import (
    TemporalCandidateRankingResult,
    TemporalCandidateRankingService,
    TemporalRankedCandidate,
)
from .candidate_temporal_evaluator import (
    TemporalCandidateEvaluation,
    TemporalCandidateEvaluator,
)
from .optimization_duration_resolver import (
    TemporalOptimizationDurationResolver,
)
from .ranking_decision_trace import (
    TemporalRankingDecisionTrace,
    TemporalRankingDecisionTraceService,
)
from .schemas import FutureCapacityRequest
from .snapshot import TemporalLearningSnapshot


class TemporalTechnicalCandidateAudit(BaseModel):
    """
    Stable audit identity for an accepted technical optimizer candidate.

    This does not alter ranking or candidate truth.
    """

    table_ids: tuple[str, ...]
    technical_score: float
    seat_waste: int
    fragmentation_minutes: int

class TemporalOptimizationResult(BaseModel):
    """
    Temporal ranking over already-accepted optimizer candidates.

    The original optimizer result remains authoritative technical truth.
    """

    available: bool

    recommended: TemporalRankedCandidate | None

    alternatives: list[TemporalRankedCandidate]

    evaluated_candidates: int

    technical_candidate_order: list[float]

    technical_candidate_audit: list[
        TemporalTechnicalCandidateAudit
    ]

    decision_trace: TemporalRankingDecisionTrace | None = None


class TemporalOptimizationOrchestrator:
    """
    Pure composition root for Temporal Optimization V1.

    Pipeline:
        technical OptimizationResult
            ->
        resolve trusted occupancy duration per accepted candidate
            ->
        evaluate each accepted candidate
            ->
        temporal candidate ranking
            ->
        separate temporal recommendation

    Invariants:
    - no candidate generation
    - no DB
    - no persistence
    - no mutation of OptimizationResult
    - no mutation of ScoredAssignment.score
    - no mutation of technical candidate start/end
    - learning/calibration context is reused across candidates
    - trusted duration is resolved independently per candidate
    - missing temporal trust context preserves technical occupancy
    - no reoptimization
    - no Brain
    - no Autopilot
    - no ML
    """

    def __init__(
        self,
        *,
        candidate_evaluator: (
            TemporalCandidateEvaluator | None
        ) = None,
        duration_resolver: (
            TemporalOptimizationDurationResolver | None
        ) = None,
    ) -> None:
        self.candidate_evaluator = (
            candidate_evaluator
            or TemporalCandidateEvaluator()
        )

        self.duration_resolver = (
            duration_resolver
            or TemporalOptimizationDurationResolver()
        )

    def evaluate(
        self,
        *,
        technical_result: OptimizationResult,
        capacity_request: FutureCapacityRequest,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
        combinations: list[TableCombination] | None,
        candidate_party_size: int,
        learning_snapshot: TemporalLearningSnapshot | None = None,
        calibration: TemporalCalibrationAssessment | None = None,
    ) -> TemporalOptimizationResult:
        candidates = self._accepted_candidates(
            technical_result=technical_result,
        )

        if not candidates:
            return TemporalOptimizationResult(
                available=False,
                recommended=None,
                alternatives=[],
                evaluated_candidates=0,
                technical_candidate_order=[],
                technical_candidate_audit=[],
            )

        evaluations: list[
            TemporalCandidateEvaluation
        ] = [
            self._evaluate_candidate(
                candidate=candidate,
                capacity_request=capacity_request,
                reservations=reservations,
                tables=tables,
                combinations=combinations,
                candidate_party_size=(
                    candidate_party_size
                ),
                learning_snapshot=learning_snapshot,
                calibration=calibration,
            )
            for candidate in candidates
        ]

        ranking = (
            TemporalCandidateRankingService.rank(
                evaluations=evaluations,
            )
        )

        decision_trace = self._decision_trace(
            ranking=ranking,
            technical_candidate=candidates[0],
        )

        return self._serialize_result(
            ranking=ranking,
            technical_candidates=candidates,
            decision_trace=decision_trace,
        )

    def _evaluate_candidate(
        self,
        *,
        candidate: ScoredAssignment,
        capacity_request: FutureCapacityRequest,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
        combinations: list[TableCombination] | None,
        candidate_party_size: int,
        learning_snapshot: TemporalLearningSnapshot | None,
        calibration: TemporalCalibrationAssessment | None,
    ) -> TemporalCandidateEvaluation:
        occupancy_duration_minutes: int | None = None

        if (
            learning_snapshot is not None
            and calibration is not None
        ):
            resolution = self.duration_resolver.resolve(
                candidate=candidate,
                party_size=candidate_party_size,
                planned_duration_minutes=(
                    self._technical_duration_minutes(
                        candidate
                    )
                ),
                snapshot=learning_snapshot,
                calibration=calibration,
            )

            occupancy_duration_minutes = (
                resolution.decision.duration_minutes
            )

        return self.candidate_evaluator.evaluate(
            request=capacity_request,
            candidate=candidate,
            reservations=reservations,
            tables=tables,
            combinations=combinations,
            candidate_party_size=(
                candidate_party_size
            ),
            candidate_occupancy_duration_minutes=(
                occupancy_duration_minutes
            ),
        )

    @staticmethod
    def _technical_duration_minutes(
        candidate: ScoredAssignment,
    ) -> int:
        duration_seconds = (
            candidate.candidate.end_at
            - candidate.candidate.start_at
        ).total_seconds()

        duration_minutes = int(
            duration_seconds // 60
        )

        if (
            duration_seconds <= 0
            or duration_seconds % 60 != 0
            or duration_minutes <= 0
        ):
            raise ValueError(
                "Technical candidate duration must be "
                "a positive whole number of minutes."
            )

        return duration_minutes

    @staticmethod
    def _accepted_candidates(
        *,
        technical_result: OptimizationResult,
    ) -> list[ScoredAssignment]:
        if (
            not technical_result.available
            or technical_result.recommended is None
        ):
            return []

        return [
            technical_result.recommended,
            *technical_result.alternatives,
        ]

    @staticmethod
    def _technical_candidate_audit(
        *,
        technical_candidates: list[ScoredAssignment],
    ) -> list[TemporalTechnicalCandidateAudit]:
        return [
            TemporalTechnicalCandidateAudit(
                table_ids=tuple(candidate.candidate.table_ids),
                technical_score=candidate.score,
                seat_waste=candidate.seat_waste,
                fragmentation_minutes=(
                    candidate.fragmentation_minutes
                ),
            )
            for candidate in technical_candidates
        ]

    @staticmethod
    def _decision_trace(
        *,
        ranking: TemporalCandidateRankingResult,
        technical_candidate: ScoredAssignment,
    ) -> TemporalRankingDecisionTrace | None:
        if not ranking.ranked:
            return None

        technical_table_ids = tuple(
            str(table_id)
            for table_id in technical_candidate.candidate.table_ids
        )

        technical_winner = next(
            (
                ranked_candidate
                for ranked_candidate in ranking.ranked
                if tuple(
                    str(table_id)
                    for table_id
                    in ranked_candidate.evaluation.candidate.table_ids
                )
                == technical_table_ids
            ),
            None,
        )

        if technical_winner is None:
            return None

        return TemporalRankingDecisionTraceService.build(
            technical_winner=technical_winner,
            temporal_winner=ranking.ranked[0],
        )

    @staticmethod
    def _serialize_result(
        *,
        ranking: TemporalCandidateRankingResult,
        technical_candidates: list[
            ScoredAssignment
        ],
        decision_trace: TemporalRankingDecisionTrace | None,
    ) -> TemporalOptimizationResult:
        ranked = ranking.ranked

        if not ranked:
            return TemporalOptimizationResult(
                available=False,
                recommended=None,
                alternatives=[],
                evaluated_candidates=0,
                technical_candidate_order=[
                    candidate.score
                    for candidate
                    in technical_candidates
                ],
                technical_candidate_audit=(
                    TemporalOptimizationOrchestrator
                    ._technical_candidate_audit(
                        technical_candidates=technical_candidates,
                    )
                ),
                decision_trace=None,
            )

        return TemporalOptimizationResult(
            available=True,
            recommended=ranked[0],
            alternatives=ranked[1:],
            evaluated_candidates=len(ranked),
            technical_candidate_order=[
                candidate.score
                for candidate
                in technical_candidates
            ],
            technical_candidate_audit=(
                TemporalOptimizationOrchestrator
                ._technical_candidate_audit(
                    technical_candidates=technical_candidates,
                )
            ),
            decision_trace=decision_trace,
        )
