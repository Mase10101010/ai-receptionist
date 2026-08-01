from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Sequence


class AssignmentKind(str, Enum):
    SINGLE_TABLE = "single_table"
    TABLE_COMBINATION = "table_combination"


@dataclass(frozen=True, slots=True)
class IntelligenceTable:
    id: str
    table_number: str
    min_capacity: int
    max_capacity: int
    area_id: str | None = None
    floor_id: str | None = None
    active: bool = True


@dataclass(frozen=True, slots=True)
class TableCombination:
    id: str
    name: str
    table_ids: tuple[str, ...]
    min_capacity: int
    max_capacity: int
    setup_minutes: int = 0
    active: bool = True


@dataclass(frozen=True, slots=True)
class ExistingReservation:
    id: str
    start_at: datetime
    end_at: datetime
    party_size: int
    table_ids: tuple[str, ...]
    status: str = "confirmed"
    locked: bool = False


@dataclass(frozen=True, slots=True)
class OptimizationRequest:
    requested_start: datetime
    party_size: int
    duration_minutes: int
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    preferred_area_id: str | None = None
    preferred_floor_id: str | None = None
    allow_combinations: bool = True
    max_alternatives: int = 5


@dataclass(frozen=True, slots=True)
class CandidateAssignment:
    kind: AssignmentKind
    resource_id: str
    table_ids: tuple[str, ...]
    start_at: datetime
    end_at: datetime
    capacity: int
    minimum_capacity: int
    area_id: str | None
    floor_id: str | None
    setup_minutes: int = 0


@dataclass(frozen=True, slots=True)
class ScoredAssignment:
    candidate: CandidateAssignment
    score: float
    seat_waste: int
    fragmentation_minutes: int
    explanation: str


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    available: bool
    recommended: ScoredAssignment | None
    alternatives: tuple[ScoredAssignment, ...] = field(default_factory=tuple)
    rejected_candidates: int = 0
