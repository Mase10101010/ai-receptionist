"""Integration tests for the read-only Spatial Intelligence API."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.main import app
from app.models.floor_feature import FloorFeature
from app.models.user import User
from tests.smart_layout.test_api import (
    _count_rules,
    _count_smart_combinations,
    _create_floor_plan_with_adjacent_tables,
    _get_workspace,
)

pytestmark = pytest.mark.asyncio


def spatial_url(restaurant_id, area_id, floor_plan_id):
    return (
        f"/api/v1/restaurants/{restaurant_id}"
        f"/service-areas/{area_id}"
        f"/floor-plans/{floor_plan_id}"
        "/smart-layout/spatial-analysis"
    )


async def test_spatial_analysis_returns_geometry_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    _, restaurant, area, tables = await _get_workspace(db_session)
    floor = await _create_floor_plan_with_adjacent_tables(
        db_session, area=area, tables=tables
    )

    wall = FloorFeature(
        floor_plan_id=floor.id,
        feature_type="wall",
        x=180,
        y=100,
        width=10,
        height=80,
        rotation=0,
        is_visible=True,
    )
    db_session.add(wall)
    await db_session.flush()

    before_rules = await _count_rules(db_session)
    before_combinations = await _count_smart_combinations(db_session)

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["floor_plan_id"] == str(floor.id)
    assert len(payload["table_feature_relationships"]) == 2
    assert len(payload["table_pair_obstacles"]) == 1

    obstacle = payload["table_pair_obstacles"][0]
    assert obstacle["has_potential_obstacles"] is True
    assert obstacle["obstacle_feature_ids"] == [str(wall.id)]

    assert await _count_rules(db_session) == before_rules
    assert (
        await _count_smart_combinations(db_session)
        == before_combinations
    )


async def test_spatial_analysis_foreign_owner_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
):
    _, restaurant, area, tables = await _get_workspace(db_session)
    floor = await _create_floor_plan_with_adjacent_tables(
        db_session, area=area, tables=tables
    )

    foreign_user = User(
        email=f"spatial-foreign-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(foreign_user)
    await db_session.flush()

    async def override_foreign_user():
        return foreign_user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_foreign_user

    try:
        response = await client.get(
            spatial_url(restaurant.id, area.id, floor.id)
        )
    finally:
        if original is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original

    assert response.status_code == 404
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0


async def test_spatial_analysis_inactive_subscription_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
):
    _, restaurant, area, tables = await _get_workspace(db_session)
    floor = await _create_floor_plan_with_adjacent_tables(
        db_session, area=area, tables=tables
    )

    restaurant.subscription_status = "inactive"
    await db_session.flush()

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 403
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0


@pytest.mark.parametrize("invalid_target", ["area", "floor"])
async def test_spatial_analysis_wrong_scope_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    invalid_target: str,
):
    _, restaurant, area, tables = await _get_workspace(db_session)
    floor = await _create_floor_plan_with_adjacent_tables(
        db_session, area=area, tables=tables
    )

    area_id = uuid.uuid4() if invalid_target == "area" else area.id
    floor_id = uuid.uuid4() if invalid_target == "floor" else floor.id

    response = await client.get(
        spatial_url(restaurant.id, area_id, floor_id)
    )

    assert response.status_code == 404
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0


async def test_spatial_advisory_reports_potential_obstacle_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    _, restaurant, area, tables = await _get_workspace(db_session)
    floor = await _create_floor_plan_with_adjacent_tables(
        db_session, area=area, tables=tables
    )

    wall = FloorFeature(
        floor_plan_id=floor.id,
        feature_type="wall",
        x=180,
        y=100,
        width=10,
        height=80,
        rotation=0,
        is_visible=True,
    )
    db_session.add(wall)
    await db_session.flush()

    before_rules = await _count_rules(db_session)
    before_combinations = await _count_smart_combinations(db_session)

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert len(payload["table_pair_advisories"]) == 1
    advisory = payload["table_pair_advisories"][0]

    assert advisory["status"] == "potential_obstacle"
    assert advisory["obstacle_feature_ids"] == [str(wall.id)]

    assert await _count_rules(db_session) == before_rules
    assert await _count_smart_combinations(db_session) == before_combinations


async def test_spatial_advisory_reports_clear_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    _, restaurant, area, tables = await _get_workspace(db_session)
    floor = await _create_floor_plan_with_adjacent_tables(
        db_session, area=area, tables=tables
    )

    before_rules = await _count_rules(db_session)
    before_combinations = await _count_smart_combinations(db_session)

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert len(payload["table_pair_advisories"]) == 1
    advisory = payload["table_pair_advisories"][0]

    assert advisory["status"] == "clear"
    assert advisory["obstacle_feature_ids"] == []

    assert await _count_rules(db_session) == before_rules
    assert await _count_smart_combinations(db_session) == before_combinations

async def test_spatial_join_assessment_returns_existing_rule_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    from app.models.table_combination_rule import (
        TableCombinationRuleStatus,
    )
    from app.repositories.table_combination_rule_repository import (
        TableCombinationRuleRepository,
    )

    _, restaurant, area, tables = await _get_workspace(db_session)

    floor = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    rule_repository = TableCombinationRuleRepository(db_session)

    rule = await rule_repository.create(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor.id,
        table_ids=[tables[0].id, tables[1].id],
        status=TableCombinationRuleStatus.CONFIRMED,
    )

    before_rules = await _count_rules(db_session)
    before_combinations = await _count_smart_combinations(db_session)

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert len(payload["join_assessments"]) == 1

    assessment = payload["join_assessments"][0]

    assert assessment["rule_id"] == str(rule.id)
    assert assessment["rule_status"] == "confirmed"
    assert assessment["spatial_status"] == "clear"
    assert assessment["requires_review"] is False
    assert assessment["obstacle_feature_ids"] == []

    assert {
        assessment["first_table_id"],
        assessment["second_table_id"],
    } == {
        str(tables[0].id),
        str(tables[1].id),
    }

    assert await _count_rules(db_session) == before_rules
    assert (
        await _count_smart_combinations(db_session)
        == before_combinations
    )

@pytest.mark.parametrize(
    "rule_status",
    ["auto", "confirmed", "blocked"],
)
async def test_spatial_join_obstacle_preserves_rule_status(
    client: AsyncClient,
    db_session: AsyncSession,
    rule_status: str,
):
    from app.models.table_combination_rule import (
        TableCombinationRuleStatus,
    )
    from app.repositories.table_combination_rule_repository import (
        TableCombinationRuleRepository,
    )

    _, restaurant, area, tables = await _get_workspace(db_session)

    floor = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    wall = FloorFeature(
        floor_plan_id=floor.id,
        feature_type="wall",
        x=180,
        y=100,
        width=10,
        height=80,
        rotation=0,
        is_visible=True,
    )
    db_session.add(wall)
    await db_session.flush()

    repository = TableCombinationRuleRepository(db_session)

    rule = await repository.create(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor.id,
        table_ids=[tables[0].id, tables[1].id],
        status=TableCombinationRuleStatus(rule_status),
    )

    before_rules = await _count_rules(db_session)
    before_combinations = await _count_smart_combinations(db_session)

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text

    assessments = response.json()["join_assessments"]

    assert len(assessments) == 1

    assessment = assessments[0]

    assert assessment["rule_id"] == str(rule.id)
    assert assessment["rule_status"] == rule_status
    assert assessment["spatial_status"] == "potential_obstacle"
    assert assessment["requires_review"] is True
    assert assessment["obstacle_feature_ids"] == [str(wall.id)]

    persisted_rule = await repository.get_by_id(
        rule_id=rule.id,
        restaurant_id=restaurant.id,
    )

    assert persisted_rule is not None
    assert persisted_rule.status == TableCombinationRuleStatus(rule_status)

    assert await _count_rules(db_session) == before_rules
    assert (
        await _count_smart_combinations(db_session)
        == before_combinations
    )

async def test_spatial_join_assessment_empty_without_rules(
    client: AsyncClient,
    db_session: AsyncSession,
):
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text
    assert response.json()["join_assessments"] == []

    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0

async def test_spatial_join_assessment_ignores_multi_table_rules(
    client: AsyncClient,
    db_session: AsyncSession,
):
    from app.models.table_combination_rule import (
        TableCombinationRuleStatus,
    )
    from app.repositories.table_combination_rule_repository import (
        TableCombinationRuleRepository,
    )

    _, restaurant, area, tables = await _get_workspace(db_session)

    assert len(tables) >= 3

    floor = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    repository = TableCombinationRuleRepository(db_session)

    rule = await repository.create(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor.id,
        table_ids=[
            tables[0].id,
            tables[1].id,
            tables[2].id,
        ],
        status=TableCombinationRuleStatus.CONFIRMED,
    )

    before_rules = await _count_rules(db_session)
    before_combinations = await _count_smart_combinations(db_session)

    response = await client.get(
        spatial_url(restaurant.id, area.id, floor.id)
    )

    assert response.status_code == 200, response.text
    assert response.json()["join_assessments"] == []

    persisted_rule = await repository.get_by_id(
        rule_id=rule.id,
        restaurant_id=restaurant.id,
    )

    assert persisted_rule is not None
    assert persisted_rule.status == TableCombinationRuleStatus.CONFIRMED
    assert len(persisted_rule.members) == 3

    assert await _count_rules(db_session) == before_rules
    assert (
        await _count_smart_combinations(db_session)
        == before_combinations
    )
