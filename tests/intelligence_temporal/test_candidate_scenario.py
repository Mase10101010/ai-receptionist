from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    ExistingReservation,
    ScoredAssignment,
)
from app.intelligence_temporal.candidate_scenario import (
    TemporalCandidateScenarioBuilder,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)


def _candidate(
    *,
    resource_id: str = "table-12",
    table_ids: tuple[str, ...] = (
        "table-12",
    ),
    start_at: datetime = NOW,
    end_at: datetime | None = None,
) -> ScoredAssignment:
    assignment = CandidateAssignment(
        kind=AssignmentKind.SINGLE_TABLE,
        resource_id=resource_id,
        table_ids=table_ids,
        start_at=start_at,
        end_at=(
            end_at
            or start_at
            + timedelta(minutes=90)
        ),
        capacity=4,
        minimum_capacity=1,
        area_id="main",
        floor_id="ground",
        setup_minutes=0,
    )

    return ScoredAssignment(
        candidate=assignment,
        score=80.0,
        seat_waste=2,
        fragmentation_minutes=10,
        explanation="Technical candidate.",
    )


def _reservation(
    reservation_id: str = "existing-1",
) -> ExistingReservation:
    return ExistingReservation(
        id=reservation_id,
        start_at=(
            NOW
            - timedelta(minutes=90)
        ),
        end_at=(
            NOW
            - timedelta(minutes=30)
        ),
        party_size=2,
        table_ids=("table-9",),
        status="confirmed",
        locked=False,
    )


def test_preserves_baseline_reservations():
    existing = _reservation()

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(),
            reservations=[existing],
            party_size=2,
        )
    )

    assert result.baseline_reservations == (
        existing,
    )


def test_candidate_scenario_adds_one_reservation():
    existing = _reservation()

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(),
            reservations=[existing],
            party_size=2,
        )
    )

    assert (
        len(result.candidate_reservations)
        == 2
    )

    assert (
        result.candidate_reservations[0]
        is existing
    )


def test_synthetic_reservation_matches_candidate():
    candidate = _candidate(
        table_ids=(
            "table-12",
            "table-13",
        ),
    )

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=[],
            party_size=5,
        )
    )

    synthetic = (
        result.candidate_reservations[-1]
    )

    assert synthetic.start_at == (
        candidate.candidate.start_at
    )

    assert synthetic.end_at == (
        candidate.candidate.end_at
    )

    assert synthetic.table_ids == (
        candidate.candidate.table_ids
    )

    assert synthetic.party_size == 5


def test_synthetic_reservation_is_locked():
    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(),
            reservations=[],
            party_size=2,
        )
    )

    synthetic = (
        result.candidate_reservations[-1]
    )

    assert synthetic.locked is True
    assert synthetic.status == "confirmed"


def test_does_not_mutate_input_list():
    existing = _reservation()

    reservations = [existing]

    (
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(),
            reservations=reservations,
            party_size=2,
        )
    )

    assert reservations == [existing]
    assert len(reservations) == 1


def test_supports_table_combination():
    candidate = _candidate(
        resource_id="combo-1",
        table_ids=(
            "table-12",
            "table-13",
        ),
    )

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=[],
            party_size=6,
        )
    )

    synthetic = (
        result.candidate_reservations[-1]
    )

    assert synthetic.table_ids == (
        "table-12",
        "table-13",
    )


def test_invalid_party_size_fails_closed():
    with pytest.raises(
        ValueError,
        match="party_size",
    ):
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(),
            reservations=[],
            party_size=0,
        )


def test_duplicate_candidate_tables_fail_closed():
    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(
                table_ids=(
                    "table-12",
                    "table-12",
                ),
            ),
            reservations=[],
            party_size=2,
        )


def test_invalid_candidate_interval_fails_closed():
    with pytest.raises(
        ValueError,
        match="end_at must be after",
    ):
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(
                end_at=NOW,
            ),
            reservations=[],
            party_size=2,
        )


def test_synthetic_id_collision_fails_closed():
    candidate = _candidate(
        resource_id="table-12",
    )

    existing = _reservation(
        reservation_id=(
            "temporal-candidate:table-12"
        ),
    )

    with pytest.raises(
        ValueError,
        match="collides",
    ):
        TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=[existing],
            party_size=2,
        )

def test_default_occupancy_preserves_technical_duration():
    candidate = _candidate()

    technical_duration_minutes = int(
        (
            candidate.candidate.end_at
            - candidate.candidate.start_at
        ).total_seconds()
        // 60
    )

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=[],
            party_size=2,
        )
    )

    synthetic = result.candidate_reservations[-1]

    assert (
        result.occupancy_duration_minutes
        == technical_duration_minutes
    )

    assert (
        synthetic.end_at
        == candidate.candidate.end_at
    )


def test_longer_temporal_occupancy_extends_only_synthetic_truth():
    candidate = _candidate()

    original_end = candidate.candidate.end_at

    technical_duration_minutes = int(
        (
            candidate.candidate.end_at
            - candidate.candidate.start_at
        ).total_seconds()
        // 60
    )

    temporal_duration_minutes = (
        technical_duration_minutes + 15
    )

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=[],
            party_size=2,
            occupancy_duration_minutes=(
                temporal_duration_minutes
            ),
        )
    )

    synthetic = result.candidate_reservations[-1]

    assert synthetic.end_at == (
        candidate.candidate.start_at
        + timedelta(
            minutes=temporal_duration_minutes,
        )
    )

    assert (
        result.occupancy_duration_minutes
        == temporal_duration_minutes
    )

    # Technical candidate remains unchanged.
    assert candidate.candidate.end_at == original_end


def test_shorter_temporal_occupancy_shortens_only_synthetic_truth():
    candidate = _candidate()

    technical_duration_minutes = int(
        (
            candidate.candidate.end_at
            - candidate.candidate.start_at
        ).total_seconds()
        // 60
    )

    temporal_duration_minutes = (
        technical_duration_minutes - 15
    )

    assert temporal_duration_minutes > 0

    result = (
        TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=[],
            party_size=2,
            occupancy_duration_minutes=(
                temporal_duration_minutes
            ),
        )
    )

    synthetic = result.candidate_reservations[-1]

    assert synthetic.end_at == (
        candidate.candidate.start_at
        + timedelta(
            minutes=temporal_duration_minutes,
        )
    )

    assert (
        candidate.candidate.end_at
        == candidate.candidate.start_at
        + timedelta(
            minutes=technical_duration_minutes,
        )
    )


def test_invalid_temporal_occupancy_fails_closed():
    with pytest.raises(
        ValueError,
        match="occupancy duration",
    ):
        TemporalCandidateScenarioBuilder.build(
            candidate=_candidate(),
            reservations=[],
            party_size=2,
            occupancy_duration_minutes=0,
        )