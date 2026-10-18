"""Integration tests for spatial preference with persisted floor geometry."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.intelligence.sqlalchemy_service import IntelligenceOptimizationService
from app.intelligence.schemas import IntelligenceAssignmentResponse
from app.intelligence_temporal.candidate_ranking import TemporalRankedCandidate
from app.intelligence_temporal.candidate_temporal_evaluator import TemporalCandidateEvaluation
from app.intelligence_temporal.temporal_ranking import TemporalRankingScore
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.floor_plan import FloorPlan
from app.models.table_placement import TablePlacement
from app.models.floor_feature import FloorFeature

pytestmark = pytest.mark.asyncio


def make_ranked(table_id, *, score=100.0, lost_slots=0):
    start = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)

    assignment = IntelligenceAssignmentResponse(
        table_ids=[table_id],
        table_numbers=["1"],
        start_at=start,
        end_at=start + timedelta(minutes=90),
        capacity=4,
        score=score,
        seat_waste=2,
        fragmentation_minutes=0,
        explanation="Technical candidate",
    )

    evaluation = TemporalCandidateEvaluation.model_construct(
        candidate=assignment,
        counterfactual=None,
        occupancy_duration_minutes=90,
    )

    ranking = TemporalRankingScore(
        base_score=score,
        temporal_penalty=0.0,
        effective_score=score,
        marginal_capacity_loss_ratio=0.0,
        lost_future_available_slots=lost_slots,
    )

    return TemporalRankedCandidate(
        evaluation=evaluation,
        ranking=ranking,
    )


async def make_geometry(db_session):
    restaurant = (
        await db_session.execute(select(Restaurant))
    ).scalars().one()

    area = (
        await db_session.execute(
            select(ServiceArea).where(
                ServiceArea.restaurant_id == restaurant.id
            )
        )
    ).scalars().one()

    tables = (
        await db_session.execute(
            select(Table)
            .where(Table.restaurant_id == restaurant.id)
            .order_by(Table.table_number)
        )
    ).scalars().all()

    assert len(tables) >= 2

    far_table, near_table = tables[:2]

    plan = FloorPlan(
        service_area_id=area.id,
        name=f"Spatial Integration {uuid4()}",
        is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    db_session.add_all([
        TablePlacement(
            floor_plan_id=plan.id,
            table_id=far_table.id,
            x=400,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
        TablePlacement(
            floor_plan_id=plan.id,
            table_id=near_table.id,
            x=0,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
        FloorFeature(
            floor_plan_id=plan.id,
            feature_type="window",
            x=100,
            y=0,
            width=40,
            height=40,
            rotation=0,
            is_visible=True,
        ),
    ])

    await db_session.flush()
    return restaurant, far_table, near_table


def make_technical_result(far_table, near_table):
    def candidate(table):
        return SimpleNamespace(
            candidate=SimpleNamespace(
                resource_id=str(table.id),
                table_ids=[str(table.id)],
            )
        )

    return SimpleNamespace(
        recommended=candidate(far_table),
        alternatives=[candidate(near_table)],
    )


async def test_closer_window_table_is_promoted(client, db_session):
    restaurant, far_table, near_table = await make_geometry(db_session)

    far = make_ranked(far_table.id)
    near = make_ranked(near_table.id)

    result = await IntelligenceOptimizationService()._apply_spatial_preference(
        session=db_session,
        restaurant_id=restaurant.id,
        preference_value="near_window",
        technical_result=make_technical_result(far_table, near_table),
        temporal_result=SimpleNamespace(
            recommended=far,
            alternatives=[near],
        ),
    )

    assert result[0].evaluation.candidate.table_ids == [near_table.id]


async def test_future_capacity_protection_is_preserved(client, db_session):
    restaurant, far_table, near_table = await make_geometry(db_session)

    far = make_ranked(far_table.id, lost_slots=0)
    near = make_ranked(near_table.id, lost_slots=2)

    result = await IntelligenceOptimizationService()._apply_spatial_preference(
        session=db_session,
        restaurant_id=restaurant.id,
        preference_value="near_window",
        technical_result=make_technical_result(far_table, near_table),
        temporal_result=SimpleNamespace(
            recommended=far,
            alternatives=[near],
        ),
    )

    assert result[0].evaluation.candidate.table_ids == [far_table.id]
