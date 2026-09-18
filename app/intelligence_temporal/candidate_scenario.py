from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.intelligence.types import (
    ExistingReservation,
    ScoredAssignment,
)


@dataclass(frozen=True, slots=True)
class TemporalCandidateScenario:
    """
    Immutable optimizer-level counterfactual scenario.

    baseline_reservations:
        Existing optimizer reservation truth.

    candidate_reservations:
        Same truth plus one synthetic reservation representing
        the candidate assignment being evaluated.

    occupancy_duration_minutes:
        Duration used only by the temporal counterfactual.
        It does not modify the technical candidate.
    """

    candidate: ScoredAssignment

    baseline_reservations: tuple[
        ExistingReservation, ...
    ]

    candidate_reservations: tuple[
        ExistingReservation, ...
    ]

    synthetic_reservation_id: str

    occupancy_duration_minutes: int


class TemporalCandidateScenarioBuilder:
    """
    Builds a pure optimizer-level counterfactual scenario.

    The technical candidate remains immutable.

    An optional temporal occupancy duration may extend or shorten
    only the synthetic reservation used by future-capacity analysis.

    Invariants:
    - no DB
    - no optimizer calls
    - no candidate generation
    - no mutation of existing reservations
    - no mutation of candidate start/end
    - no ranking
    - no score changes
    - no persistence
    - no Brain
    - no Autopilot
    """

    SYNTHETIC_ID_PREFIX = "temporal-candidate:"

    @classmethod
    def build(
        cls,
        *,
        candidate: ScoredAssignment,
        reservations: (
            list[ExistingReservation]
            | tuple[ExistingReservation, ...]
        ),
        party_size: int,
        occupancy_duration_minutes: int | None = None,
    ) -> TemporalCandidateScenario:
        if party_size <= 0:
            raise ValueError(
                "Candidate scenario party_size must "
                "be positive."
            )

        assignment = candidate.candidate

        if not assignment.table_ids:
            raise ValueError(
                "Candidate scenario requires at least "
                "one table."
            )

        if (
            len(set(assignment.table_ids))
            != len(assignment.table_ids)
        ):
            raise ValueError(
                "Candidate scenario table_ids must "
                "be unique."
            )

        if assignment.end_at <= assignment.start_at:
            raise ValueError(
                "Candidate scenario end_at must be "
                "after start_at."
            )

        technical_duration_minutes = int(
            (
                assignment.end_at
                - assignment.start_at
            ).total_seconds()
            // 60
        )

        if technical_duration_minutes <= 0:
            raise ValueError(
                "Technical candidate duration must "
                "be positive."
            )

        effective_duration_minutes = (
            occupancy_duration_minutes
            if occupancy_duration_minutes is not None
            else technical_duration_minutes
        )

        if effective_duration_minutes <= 0:
            raise ValueError(
                "Temporal occupancy duration must "
                "be positive."
            )

        baseline = tuple(reservations)

        synthetic_id = (
            f"{cls.SYNTHETIC_ID_PREFIX}"
            f"{assignment.resource_id}"
        )

        existing_ids = {
            reservation.id
            for reservation in baseline
        }

        if synthetic_id in existing_ids:
            raise ValueError(
                "Synthetic candidate reservation ID "
                "collides with an existing reservation."
            )

        synthetic_end_at = (
            assignment.start_at
            + timedelta(
                minutes=effective_duration_minutes,
            )
        )

        synthetic_reservation = ExistingReservation(
            id=synthetic_id,
            start_at=assignment.start_at,
            end_at=synthetic_end_at,
            party_size=party_size,
            table_ids=assignment.table_ids,
            status="confirmed",
            locked=True,
        )

        return TemporalCandidateScenario(
            candidate=candidate,
            baseline_reservations=baseline,
            candidate_reservations=(
                *baseline,
                synthetic_reservation,
            ),
            synthetic_reservation_id=synthetic_id,
            occupancy_duration_minutes=(
                effective_duration_minutes
            ),
        )