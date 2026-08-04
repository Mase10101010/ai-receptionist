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

@dataclass(frozen=True, slots=True)
class ReoptimizationRequest:
    requested_start: datetime
    party_size: int
    duration_minutes: int
    reservation_id: str | None = None
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    preferred_area_id: str | None = None
    preferred_floor_id: str | None = None
    allow_combinations: bool = True

    # Limiti di sicurezza per la prima versione assistita.
    max_reservations_to_move: int = 2
    max_plans: int = 5


@dataclass(frozen=True, slots=True)
class ReservationMove:
    reservation_id: str

    from_table_ids: tuple[str, ...]
    to_table_ids: tuple[str, ...]

    party_size: int
    start_at: datetime
    end_at: datetime

    destination_capacity: int
    seat_waste: int

    explanation: str


@dataclass(frozen=True, slots=True)
class ReoptimizationPlan:
    new_reservation_assignment: ScoredAssignment

    moves: tuple[ReservationMove, ...]

    score: float
    total_seat_waste: int
    moved_reservations_count: int

    explanation: str


@dataclass(frozen=True, slots=True)
class ReoptimizationResult:
    available: bool

    recommended: ReoptimizationPlan | None

    alternatives: tuple[ReoptimizationPlan, ...] = field(
        default_factory=tuple,
    )

    evaluated_plans: int = 0
    rejected_plans: int = 0