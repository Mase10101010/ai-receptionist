from app.intelligence.temporal_trace_mapper import (
    IntelligenceTemporalTraceMapper,
)
from app.intelligence_temporal.ranking_decision_trace import (
    TemporalRankingCandidateTrace,
    TemporalRankingDecisionTrace,
)


def _candidate(
    *,
    table_id: str,
    technical_score: float,
    effective_score: float,
    loss_ratio: float,
    lost_slots: int,
) -> TemporalRankingCandidateTrace:
    return TemporalRankingCandidateTrace(
        table_ids=(table_id,),
        technical_score=technical_score,
        effective_score=effective_score,
        marginal_capacity_loss_ratio=loss_ratio,
        lost_future_available_slots=lost_slots,
    )


def test_maps_temporal_decision_trace_without_changing_values():
    trace = TemporalRankingDecisionTrace(
        technical_winner=_candidate(
            table_id="table-1",
            technical_score=92.0,
            effective_score=82.0,
            loss_ratio=0.4,
            lost_slots=4,
        ),
        temporal_winner=_candidate(
            table_id="table-2",
            technical_score=88.0,
            effective_score=88.0,
            loss_ratio=0.0,
            lost_slots=0,
        ),
        recommendation_changed=True,
    )

    result = IntelligenceTemporalTraceMapper.map(
        trace=trace,
    )

    assert result.recommendation_changed is True

    assert result.technical_winner.table_ids == (
        "table-1",
    )
    assert result.technical_winner.technical_score == 92.0
    assert result.technical_winner.effective_score == 82.0
    assert (
        result.technical_winner
        .marginal_capacity_loss_ratio
        == 0.4
    )
    assert (
        result.technical_winner
        .lost_future_available_slots
        == 4
    )

    assert result.temporal_winner.table_ids == (
        "table-2",
    )
    assert result.temporal_winner.technical_score == 88.0
    assert result.temporal_winner.effective_score == 88.0
    assert (
        result.temporal_winner
        .marginal_capacity_loss_ratio
        == 0.0
    )
    assert (
        result.temporal_winner
        .lost_future_available_slots
        == 0
    )


def test_maps_unchanged_recommendation():
    candidate = _candidate(
        table_id="table-1",
        technical_score=90.0,
        effective_score=90.0,
        loss_ratio=0.0,
        lost_slots=0,
    )

    trace = TemporalRankingDecisionTrace(
        technical_winner=candidate,
        temporal_winner=candidate,
        recommendation_changed=False,
    )

    result = IntelligenceTemporalTraceMapper.map(
        trace=trace,
    )

    assert result.recommendation_changed is False
    assert (
        result.technical_winner.table_ids
        == result.temporal_winner.table_ids
    )


def test_optimize_response_defaults_to_no_temporal_trace():
    from app.intelligence.schemas import (
        IntelligenceOptimizeResponse,
    )

    response = IntelligenceOptimizeResponse(
        available=False,
        recommended=None,
        alternatives=[],
        rejected_candidates=0,
    )

    assert response.temporal_decision_trace is None