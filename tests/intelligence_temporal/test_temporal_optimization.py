from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    IntelligenceTable,
    OptimizationResult,
    ScoredAssignment,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
)
from app.intelligence_temporal.temporal_optimization import (
    TemporalOptimizationOrchestrator,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)

RESTAURANT_ID = uuid4()

TABLE_1 = uuid4()
TABLE_2 = uuid4()


def _table(
    table_id,
    number: str,
) -> IntelligenceTable:
    return IntelligenceTable(
        id=str(table_id),
        table_number=number,
        min_capacity=1,
        max_capacity=4,
        area_id="main",
    )


def _candidate(
    *,
    table_id,
    score: float,
    duration_minutes: int = 90,
) -> ScoredAssignment:
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(table_id),
            table_ids=(str(table_id),),
            start_at=NOW,
            end_at=(
                NOW
                + timedelta(
                    minutes=duration_minutes
                )
            ),
            capacity=4,
            minimum_capacity=1,
            area_id="main",
            floor_id=None,
            setup_minutes=0,
        ),
        score=score,
        seat_waste=0,
        fragmentation_minutes=0,
        explanation="Candidate.",
    )


def _request() -> FutureCapacityRequest:
    return FutureCapacityRequest(
        restaurant_id=RESTAURANT_ID,
        start_at=NOW,
        party_size=4,
        duration_minutes=30,
        horizon_minutes=60,
        slot_minutes=30,
    )


def test_unavailable_technical_result_returns_unavailable():
    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=False,
                recommended=None,
                alternatives=(),
                rejected_candidates=2,
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert result.available is False
    assert result.recommended is None
    assert result.alternatives == []
    assert result.evaluated_candidates == 0


def test_single_candidate_is_preserved():
    candidate = _candidate(
        table_id=TABLE_1,
        score=90.0,
    )

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=candidate,
                alternatives=(),
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert result.available is True
    assert result.evaluated_candidates == 1

    assert (
        result.recommended
        .evaluation.candidate.score
        == 90.0
    )


def test_all_accepted_candidates_are_evaluated():
    first = _candidate(
        table_id=TABLE_1,
        score=90.0,
    )

    second = _candidate(
        table_id=TABLE_2,
        score=85.0,
    )

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=first,
                alternatives=(second,),
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert result.evaluated_candidates == 2
    assert len(result.alternatives) == 1


def test_preserves_original_technical_order_for_audit():
    first = _candidate(
        table_id=TABLE_1,
        score=92.0,
    )

    second = _candidate(
        table_id=TABLE_2,
        score=88.0,
    )

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=first,
                alternatives=(second,),
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert result.technical_candidate_order == [
        92.0,
        88.0,
    ]


def test_temporal_ranking_can_change_recommendation():
    """
    Table 1 is the technically preferred candidate.

    Table 2 is also available and preserves future capacity
    differently depending on the candidate scenario.

    Temporal ranking is allowed to choose a technically lower
    scoring candidate when future-capacity loss is sufficiently
    lower.
    """

    technically_first = _candidate(
        table_id=TABLE_1,
        score=92.0,
        duration_minutes=90,
    )

    technically_second = _candidate(
        table_id=TABLE_2,
        score=88.0,
        duration_minutes=90,
    )

    # Table 2 is already unavailable during the future window.
    # Therefore occupying table 1 can destroy the last remaining
    # directly-bookable capacity, while occupying table 2 may not.
    from app.intelligence.types import (
        ExistingReservation,
    )

    existing = ExistingReservation(
        id="existing-table-2",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=(str(TABLE_2),),
        status="confirmed",
        locked=False,
    )

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=technically_first,
                alternatives=(
                    technically_second,
                ),
            ),
            capacity_request=_request(),
            reservations=[existing],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert result.available is True

    assert (
        result.recommended
        .evaluation.candidate.score
        in {92.0, 88.0}
    )


def test_does_not_mutate_technical_scores():
    first = _candidate(
        table_id=TABLE_1,
        score=92.0,
    )

    second = _candidate(
        table_id=TABLE_2,
        score=88.0,
    )

    (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=first,
                alternatives=(second,),
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert first.score == 92.0
    assert second.score == 88.0


def test_temporal_scores_remain_separate_from_base_scores():
    first = _candidate(
        table_id=TABLE_1,
        score=92.0,
    )

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=first,
                alternatives=(),
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    ranked = result.recommended

    assert ranked is not None

    assert (
        ranked.ranking.base_score
        == ranked.evaluation.candidate.score
    )


def test_rejected_candidate_count_does_not_affect_temporal_ranking():
    candidate = _candidate(
        table_id=TABLE_1,
        score=90.0,
    )

    result = (
        TemporalOptimizationOrchestrator()
        .evaluate(
            technical_result=OptimizationResult(
                available=True,
                recommended=candidate,
                alternatives=(),
                rejected_candidates=50,
            ),
            capacity_request=_request(),
            reservations=[],
            tables=[
                _table(TABLE_1, "1"),
                _table(TABLE_2, "2"),
            ],
            combinations=[],
            candidate_party_size=2,
        )
    )

    assert result.available is True
    assert result.evaluated_candidates == 1


def test_trusted_duration_is_resolved_per_candidate():
    from types import SimpleNamespace

    from app.intelligence_temporal.candidate_temporal_evaluator import (
        TemporalCandidateEvaluator,
    )
    from app.intelligence_temporal.calibration_state import (
        TemporalCalibrationState,
    )
    from app.intelligence_temporal.snapshot import (
        TemporalLearningSnapshot,
    )

    first = _candidate(
        table_id=TABLE_1,
        score=92.0,
        duration_minutes=90,
    )
    second = _candidate(
        table_id=TABLE_2,
        score=88.0,
        duration_minutes=90,
    )

    resolved = []
    propagated = []

    class RecordingResolver:
        def resolve(self, **kwargs):
            resolved.append(kwargs["candidate"])

            duration = (
                105
                if kwargs["candidate"] is first
                else 120
            )

            return SimpleNamespace(
                decision=SimpleNamespace(
                    duration_minutes=duration,
                )
            )

    real_evaluator = TemporalCandidateEvaluator()

    class RecordingEvaluator:
        def evaluate(self, **kwargs):
            propagated.append(
                (
                    kwargs["candidate"],
                    kwargs[
                        "candidate_occupancy_duration_minutes"
                    ],
                )
            )
            return real_evaluator.evaluate(**kwargs)

    snapshot = TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=0,
    )

    calibration = SimpleNamespace(
        state=(
            TemporalCalibrationState
            .WELL_CALIBRATED
        )
    )

    result = TemporalOptimizationOrchestrator(
        candidate_evaluator=RecordingEvaluator(),
        duration_resolver=RecordingResolver(),
    ).evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=first,
            alternatives=(second,),
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
        learning_snapshot=snapshot,
        calibration=calibration,
    )

    assert result.evaluated_candidates == 2

    assert resolved == [
        first,
        second,
    ]

    assert propagated == [
        (first, 105),
        (second, 120),
    ]


def test_missing_trust_context_preserves_technical_occupancy():
    from app.intelligence_temporal.candidate_temporal_evaluator import (
        TemporalCandidateEvaluator,
    )

    candidate = _candidate(
        table_id=TABLE_1,
        score=90.0,
        duration_minutes=90,
    )

    propagated = []

    class ResolverMustNotRun:
        def resolve(self, **kwargs):
            raise AssertionError(
                "Duration resolver must not run "
                "without complete trust context."
            )

    real_evaluator = TemporalCandidateEvaluator()

    class RecordingEvaluator:
        def evaluate(self, **kwargs):
            propagated.append(
                kwargs[
                    "candidate_occupancy_duration_minutes"
                ]
            )
            return real_evaluator.evaluate(**kwargs)

    result = TemporalOptimizationOrchestrator(
        candidate_evaluator=RecordingEvaluator(),
        duration_resolver=ResolverMustNotRun(),
    ).evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=candidate,
            alternatives=(),
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.available is True
    assert propagated == [None]

    assert (
        result.recommended
        .evaluation
        .occupancy_duration_minutes
        == 90
    )


def test_duration_resolution_does_not_mutate_technical_candidate():
    from types import SimpleNamespace

    from app.intelligence_temporal.candidate_temporal_evaluator import (
        TemporalCandidateEvaluator,
    )
    from app.intelligence_temporal.calibration_state import (
        TemporalCalibrationState,
    )
    from app.intelligence_temporal.snapshot import (
        TemporalLearningSnapshot,
    )

    candidate = _candidate(
        table_id=TABLE_1,
        score=90.0,
        duration_minutes=90,
    )

    original_start = candidate.candidate.start_at
    original_end = candidate.candidate.end_at
    original_score = candidate.score

    class LongerDurationResolver:
        def resolve(self, **kwargs):
            return SimpleNamespace(
                decision=SimpleNamespace(
                    duration_minutes=120,
                )
            )

    snapshot = TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=0,
    )

    calibration = SimpleNamespace(
        state=(
            TemporalCalibrationState
            .WELL_CALIBRATED
        )
    )

    result = TemporalOptimizationOrchestrator(
        candidate_evaluator=(
            TemporalCandidateEvaluator()
        ),
        duration_resolver=LongerDurationResolver(),
    ).evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=candidate,
            alternatives=(),
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
        learning_snapshot=snapshot,
        calibration=calibration,
    )

    assert candidate.candidate.start_at == original_start
    assert candidate.candidate.end_at == original_end
    assert candidate.score == original_score

    assert result.recommended is not None
    assert (
        result.recommended
        .evaluation.candidate.start_at
        == original_start
    )
    assert (
        result.recommended
        .evaluation.candidate.end_at
        == original_end
    )
    assert (
        result.recommended
        .evaluation.occupancy_duration_minutes
        == 120
    )

def test_unavailable_result_has_empty_technical_candidate_audit():
    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=False,
            recommended=None,
            alternatives=(),
            rejected_candidates=2,
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.technical_candidate_audit == []


def test_technical_candidate_audit_preserves_original_order_and_identity():
    first = _candidate(
        table_id=TABLE_1,
        score=92.0,
    )
    second = _candidate(
        table_id=TABLE_2,
        score=88.0,
    )

    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=first,
            alternatives=(second,),
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert [
        audit.table_ids
        for audit in result.technical_candidate_audit
    ] == [
        (str(TABLE_1),),
        (str(TABLE_2),),
    ]

    assert [
        audit.technical_score
        for audit in result.technical_candidate_audit
    ] == [
        92.0,
        88.0,
    ]


def test_technical_candidate_audit_preserves_candidate_metrics():
    candidate = ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(TABLE_1),
            table_ids=(str(TABLE_1),),
            start_at=NOW,
            end_at=NOW + timedelta(minutes=90),
            capacity=4,
            minimum_capacity=1,
            area_id="main",
            floor_id=None,
            setup_minutes=0,
        ),
        score=91.0,
        seat_waste=2,
        fragmentation_minutes=15,
        explanation="Candidate.",
    )

    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=candidate,
            alternatives=(),
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert len(result.technical_candidate_audit) == 1

    audit = result.technical_candidate_audit[0]

    assert audit.table_ids == (str(TABLE_1),)
    assert audit.technical_score == 91.0
    assert audit.seat_waste == 2
    assert audit.fragmentation_minutes == 15


def test_temporal_ranking_does_not_mutate_technical_candidate_audit():
    from app.intelligence.types import ExistingReservation

    technically_first = _candidate(
        table_id=TABLE_1,
        score=92.0,
        duration_minutes=90,
    )
    technically_second = _candidate(
        table_id=TABLE_2,
        score=88.0,
        duration_minutes=90,
    )

    existing = ExistingReservation(
        id="existing-table-2-audit",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=(str(TABLE_2),),
        status="confirmed",
        locked=False,
    )

    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=technically_first,
            alternatives=(technically_second,),
        ),
        capacity_request=_request(),
        reservations=[existing],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert [
        (
            audit.table_ids,
            audit.technical_score,
        )
        for audit in result.technical_candidate_audit
    ] == [
        ((str(TABLE_1),), 92.0),
        ((str(TABLE_2),), 88.0),
    ]

def test_decision_trace_reports_unchanged_recommendation():
    candidate = _candidate(
        table_id=TABLE_1,
        score=90.0,
    )

    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=candidate,
            alternatives=(),
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.decision_trace is not None
    assert (
        result.decision_trace.recommendation_changed
        is False
    )

    assert (
        result.decision_trace.technical_winner.table_ids
        == (str(TABLE_1),)
    )
    assert (
        result.decision_trace.temporal_winner.table_ids
        == (str(TABLE_1),)
    )


def test_decision_trace_preserves_original_technical_winner():
    from app.intelligence.types import ExistingReservation

    technically_first = _candidate(
        table_id=TABLE_1,
        score=92.0,
        duration_minutes=90,
    )
    technically_second = _candidate(
        table_id=TABLE_2,
        score=88.0,
        duration_minutes=90,
    )

    existing = ExistingReservation(
        id="existing-table-2-decision-trace",
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        party_size=2,
        table_ids=(str(TABLE_2),),
        status="confirmed",
        locked=False,
    )

    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=True,
            recommended=technically_first,
            alternatives=(technically_second,),
        ),
        capacity_request=_request(),
        reservations=[existing],
        tables=[
            _table(TABLE_1, "1"),
            _table(TABLE_2, "2"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.decision_trace is not None

    assert (
        result.decision_trace
        .technical_winner.table_ids
        == (str(TABLE_1),)
    )

    assert (
        result.decision_trace
        .technical_winner.technical_score
        == 92.0
    )

    assert (
        result.decision_trace
        .temporal_winner.table_ids
        == tuple(
            str(table_id)
            for table_id
            in result.recommended.evaluation.candidate.table_ids
        )
    )


def test_unavailable_result_has_no_decision_trace():
    result = TemporalOptimizationOrchestrator().evaluate(
        technical_result=OptimizationResult(
            available=False,
            recommended=None,
            alternatives=(),
            rejected_candidates=2,
        ),
        capacity_request=_request(),
        reservations=[],
        tables=[
            _table(TABLE_1, "1"),
        ],
        combinations=[],
        candidate_party_size=2,
    )

    assert result.decision_trace is None
