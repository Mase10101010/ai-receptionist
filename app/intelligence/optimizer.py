from __future__ import annotations

from .candidate_generator import generate_candidates
from .interval_engine import (
    calculate_fragmentation_minutes,
    is_assignment_available,
)
from .scoring import score_candidate
from .types import (
    ExistingReservation,
    IntelligenceTable,
    OptimizationRequest,
    OptimizationResult,
    ScoredAssignment,
    TableCombination,
)


class ReservationOptimizer:
    """Deterministic first version of the Alias Intelligence Engine.

    It never writes to the database and never mutates reservations.
    """

    def optimize(
        self,
        request: OptimizationRequest,
        tables: list[IntelligenceTable],
        reservations: list[ExistingReservation],
        combinations: list[TableCombination] | None = None,
    ) -> OptimizationResult:
        combinations = combinations or []

        candidates = generate_candidates(
            request=request,
            tables=tables,
            combinations=combinations,
        )

        accepted: list[ScoredAssignment] = []
        rejected_candidates = 0

        for candidate in candidates:
            available = is_assignment_available(
                table_ids=candidate.table_ids,
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                reservations=reservations,
                buffer_before_minutes=request.buffer_before_minutes,
                buffer_after_minutes=request.buffer_after_minutes,
                setup_minutes=candidate.setup_minutes,
            )

            if not available:
                rejected_candidates += 1
                continue

            fragmentation_minutes = calculate_fragmentation_minutes(
                table_ids=candidate.table_ids,
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                reservations=reservations,
                useful_gap_threshold_minutes=request.duration_minutes,
            )

            score, seat_waste, explanation = score_candidate(
                candidate=candidate,
                request=request,
                fragmentation_minutes=fragmentation_minutes,
            )

            accepted.append(
                ScoredAssignment(
                    candidate=candidate,
                    score=score,
                    seat_waste=seat_waste,
                    fragmentation_minutes=fragmentation_minutes,
                    explanation=explanation,
                ),
            )

        accepted.sort(
            key=lambda item: (
                -item.score,
                item.seat_waste,
                len(item.candidate.table_ids),
                item.candidate.resource_id,
            ),
        )

        limited = accepted[: max(request.max_alternatives, 1)]

        return OptimizationResult(
            available=bool(limited),
            recommended=limited[0] if limited else None,
            alternatives=tuple(limited[1:]),
            rejected_candidates=rejected_candidates,
        )
