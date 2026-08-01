from __future__ import annotations

from .types import CandidateAssignment, OptimizationRequest


def score_candidate(
    candidate: CandidateAssignment,
    request: OptimizationRequest,
    fragmentation_minutes: int,
) -> tuple[float, int, str]:
    seat_waste = max(candidate.capacity - request.party_size, 0)

    score = 100.0

    # Preserve larger tables for larger parties.
    score -= seat_waste * 4.0

    # Avoid creating dead gaps between bookings.
    score -= fragmentation_minutes * 0.35

    # Prefer a single physical table over combinations.
    if len(candidate.table_ids) > 1:
        score -= 8.0
        score -= max(len(candidate.table_ids) - 2, 0) * 3.0

    # Account for setup effort.
    score -= candidate.setup_minutes * 0.25

    if (
        request.preferred_area_id
        and candidate.area_id != request.preferred_area_id
    ):
        score -= 12.0

    if (
        request.preferred_floor_id
        and candidate.floor_id != request.preferred_floor_id
    ):
        score -= 12.0

    explanation_parts = []

    if seat_waste == 0:
        explanation_parts.append("exact capacity fit")
    elif seat_waste == 1:
        explanation_parts.append("one unused seat")
    else:
        explanation_parts.append(f"{seat_waste} unused seats")

    if fragmentation_minutes == 0:
        explanation_parts.append("no dead time created")
    else:
        explanation_parts.append(
            f"{fragmentation_minutes} minutes of fragmentation",
        )

    if len(candidate.table_ids) == 1:
        explanation_parts.append("single-table assignment")
    else:
        explanation_parts.append(
            f"combines {len(candidate.table_ids)} tables",
        )

    return round(score, 2), seat_waste, "; ".join(explanation_parts)
