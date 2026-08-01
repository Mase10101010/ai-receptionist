from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from .types import (
    AssignmentKind,
    CandidateAssignment,
    IntelligenceTable,
    OptimizationRequest,
    TableCombination,
)


def generate_candidates(
    request: OptimizationRequest,
    tables: Iterable[IntelligenceTable],
    combinations: Iterable[TableCombination],
) -> list[CandidateAssignment]:
    end_at = request.requested_start + timedelta(
        minutes=request.duration_minutes,
    )

    table_map = {table.id: table for table in tables if table.active}
    candidates: list[CandidateAssignment] = []

    for table in table_map.values():
        if not (
            table.min_capacity
            <= request.party_size
            <= table.max_capacity
        ):
            continue

        candidates.append(
            CandidateAssignment(
                kind=AssignmentKind.SINGLE_TABLE,
                resource_id=table.id,
                table_ids=(table.id,),
                start_at=request.requested_start,
                end_at=end_at,
                capacity=table.max_capacity,
                minimum_capacity=table.min_capacity,
                area_id=table.area_id,
                floor_id=table.floor_id,
            ),
        )

    if not request.allow_combinations:
        return candidates

    for combination in combinations:
        if not combination.active:
            continue

        if not (
            combination.min_capacity
            <= request.party_size
            <= combination.max_capacity
        ):
            continue

        members = [table_map.get(table_id) for table_id in combination.table_ids]
        if any(member is None for member in members):
            continue

        area_ids = {member.area_id for member in members if member is not None}
        floor_ids = {member.floor_id for member in members if member is not None}

        # A physical combination cannot span different service areas or floors.
        if len(area_ids) > 1 or len(floor_ids) > 1:
            continue

        candidates.append(
            CandidateAssignment(
                kind=AssignmentKind.TABLE_COMBINATION,
                resource_id=combination.id,
                table_ids=combination.table_ids,
                start_at=request.requested_start,
                end_at=end_at,
                capacity=combination.max_capacity,
                minimum_capacity=combination.min_capacity,
                area_id=next(iter(area_ids), None),
                floor_id=next(iter(floor_ids), None),
                setup_minutes=combination.setup_minutes,
            ),
        )

    return candidates
