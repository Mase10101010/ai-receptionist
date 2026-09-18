import uuid

import pytest

from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_combination import (
    TableCombination,
    TableCombinationMember,
)
from app.models.table_combination_rule import (
    TableCombinationRuleStatus,
)
from app.models.user import User
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)
from app.services.smart_layout.materialization import (
    SmartLayoutMaterializationService,
)

async def build_materialization_repository_scenario(
    db_session,
):
    user = User(
        email=f"materialization-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Materialization Restaurant",
        slug=f"materialization-{uuid.uuid4()}",
        opening_hour=0,
        closing_hour=23,
        number_of_tables=2,
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(restaurant)
    await db_session.flush()

    area = ServiceArea(
        restaurant_id=restaurant.id,
        name="Main",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(area)
    await db_session.flush()

    floor_plan = FloorPlan(
        service_area_id=area.id,
        name="Default",
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    tables = [
        Table(
            restaurant_id=restaurant.id,
            service_area_id=area.id,
            table_code=f"MAT-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    rule_repository = TableCombinationRuleRepository(
        db_session
    )

    rule = await rule_repository.create(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        table_ids=[
            tables[0].id,
            tables[1].id,
        ],
        status=TableCombinationRuleStatus.AUTO,
    )

    return {
        "restaurant": restaurant,
        "area": area,
        "floor_plan": floor_plan,
        "tables": tables,
        "rule": rule,
    }


@pytest.mark.asyncio
async def test_get_by_smart_layout_rule_id_returns_materialized_combination(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    tables = scenario["tables"]
    rule = scenario["rule"]

    repository = TableCombinationRepository(
        db_session
    )

    combination = TableCombination(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        smart_layout_rule_id=rule.id,
        name=f"Smart Layout {rule.id}",
        min_capacity=1,
        max_capacity=sum(
            table.seats for table in tables
        ),
        setup_minutes=0,
        is_active=True,
        members=[
            TableCombinationMember(
                table_id=table.id,
                sort_order=index,
            )
            for index, table in enumerate(tables)
        ],
    )

    await repository.create(
        combination
    )

    found = (
        await repository.get_by_smart_layout_rule_id(
            smart_layout_rule_id=rule.id,
            restaurant_id=restaurant.id,
        )
    )

    assert found is not None
    assert found.id == combination.id
    assert found.smart_layout_rule_id == rule.id

    assert {
        member.table_id
        for member in found.members
    } == {
        table.id
        for table in tables
    }


@pytest.mark.asyncio
async def test_manual_combination_is_not_smart_layout_materialization(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    tables = scenario["tables"]
    rule = scenario["rule"]

    repository = TableCombinationRepository(
        db_session
    )

    manual = TableCombination(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        name=f"Manual {uuid.uuid4()}",
        min_capacity=1,
        max_capacity=sum(
            table.seats for table in tables
        ),
        setup_minutes=0,
        is_active=True,
        members=[
            TableCombinationMember(
                table_id=table.id,
                sort_order=index,
            )
            for index, table in enumerate(tables)
        ],
    )

    await repository.create(
        manual
    )

    found = (
        await repository.get_by_smart_layout_rule_id(
            smart_layout_rule_id=rule.id,
            restaurant_id=restaurant.id,
        )
    )

    assert manual.smart_layout_rule_id is None
    assert found is None

@pytest.mark.asyncio
async def test_auto_rule_materializes_executable_combination(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    rule = scenario["rule"]
    tables = scenario["tables"]

    repository = TableCombinationRepository(
        db_session
    )
    service = SmartLayoutMaterializationService(
        combination_repository=repository,
    )

    result = await service.materialize_rule(
        rule
    )

    assert result.created is True
    assert result.preserved is False
    assert result.deleted is False
    assert result.skipped is False
    assert result.combination is not None

    combination = result.combination

    assert combination.smart_layout_rule_id == rule.id
    assert combination.is_active is True
    assert combination.min_capacity == 1
    assert combination.max_capacity == sum(
        table.seats for table in tables
    )
    assert combination.setup_minutes == 0

    assert {
        member.table_id
        for member in combination.members
    } == {
        table.id
        for table in tables
    }


@pytest.mark.asyncio
async def test_confirmed_rule_materializes_executable_combination(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    rule_repository = TableCombinationRuleRepository(
        db_session
    )

    rule = await rule_repository.set_status(
        scenario["rule"],
        TableCombinationRuleStatus.CONFIRMED,
    )

    repository = TableCombinationRepository(
        db_session
    )
    service = SmartLayoutMaterializationService(
        combination_repository=repository,
    )

    result = await service.materialize_rule(
        rule
    )

    assert result.created is True
    assert result.deleted is False
    assert result.skipped is False
    assert result.combination is not None
    assert (
        result.combination.smart_layout_rule_id
        == rule.id
    )


@pytest.mark.asyncio
async def test_materialization_is_idempotent(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    rule = scenario["rule"]

    repository = TableCombinationRepository(
        db_session
    )
    service = SmartLayoutMaterializationService(
        combination_repository=repository,
    )

    first = await service.materialize_rule(
        rule
    )
    second = await service.materialize_rule(
        rule
    )

    assert first.created is True

    assert second.created is False
    assert second.preserved is True
    assert second.deleted is False
    assert second.skipped is False

    assert first.combination is not None
    assert second.combination is not None

    assert (
        first.combination.id
        == second.combination.id
    )

    combinations = await repository.list_by_restaurant(
        restaurant_id=scenario["restaurant"].id,
        include_inactive=True,
    )

    smart_layout_combinations = [
        combination
        for combination in combinations
        if combination.smart_layout_rule_id
        == rule.id
    ]

    assert len(smart_layout_combinations) == 1


@pytest.mark.asyncio
async def test_blocked_rule_is_not_materialized(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    rule_repository = TableCombinationRuleRepository(
        db_session
    )

    rule = await rule_repository.set_status(
        scenario["rule"],
        TableCombinationRuleStatus.BLOCKED,
    )

    repository = TableCombinationRepository(
        db_session
    )
    service = SmartLayoutMaterializationService(
        combination_repository=repository,
    )

    result = await service.materialize_rule(
        rule
    )

    assert result.created is False
    assert result.preserved is False
    assert result.deleted is False
    assert result.skipped is True
    assert result.combination is None

    found = (
        await repository.get_by_smart_layout_rule_id(
            smart_layout_rule_id=rule.id,
            restaurant_id=rule.restaurant_id,
        )
    )

    assert found is None

@pytest.mark.asyncio
async def test_blocked_rule_dematerializes_existing_combination(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    rule = scenario["rule"]

    combination_repository = TableCombinationRepository(
        db_session
    )
    rule_repository = TableCombinationRuleRepository(
        db_session
    )

    service = SmartLayoutMaterializationService(
        combination_repository=combination_repository,
    )

    created = await service.materialize_rule(
        rule
    )

    assert created.created is True
    assert created.combination is not None

    rule = await rule_repository.set_status(
        rule,
        TableCombinationRuleStatus.BLOCKED,
    )

    result = await service.materialize_rule(
        rule
    )

    assert result.created is False
    assert result.preserved is False
    assert result.deleted is True
    assert result.skipped is False
    assert result.combination is None

    found = (
        await combination_repository
        .get_by_smart_layout_rule_id(
            smart_layout_rule_id=rule.id,
            restaurant_id=rule.restaurant_id,
        )
    )

    assert found is None

@pytest.mark.asyncio
async def test_blocking_smart_rule_does_not_delete_manual_combination(
    db_session,
):
    scenario = (
        await build_materialization_repository_scenario(
            db_session
        )
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    tables = scenario["tables"]
    rule = scenario["rule"]

    combination_repository = TableCombinationRepository(
        db_session
    )
    rule_repository = TableCombinationRuleRepository(
        db_session
    )

    manual = TableCombination(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        name=f"Manual {uuid.uuid4()}",
        min_capacity=1,
        max_capacity=sum(
            table.seats for table in tables
        ),
        setup_minutes=0,
        is_active=True,
        members=[
            TableCombinationMember(
                table_id=table.id,
                sort_order=index,
            )
            for index, table in enumerate(tables)
        ],
    )

    manual = await combination_repository.create(
        manual
    )

    service = SmartLayoutMaterializationService(
        combination_repository=combination_repository,
    )

    smart_result = await service.materialize_rule(
        rule
    )

    assert smart_result.created is True
    assert smart_result.combination is not None

    rule = await rule_repository.set_status(
        rule,
        TableCombinationRuleStatus.BLOCKED,
    )

    blocked_result = await service.materialize_rule(
        rule
    )

    assert blocked_result.deleted is True

    manual_after = (
        await combination_repository.get_by_id(
            combination_id=manual.id,
            restaurant_id=restaurant.id,
        )
    )

    smart_after = (
        await combination_repository
        .get_by_smart_layout_rule_id(
            smart_layout_rule_id=rule.id,
            restaurant_id=restaurant.id,
        )
    )

    assert manual_after is not None
    assert manual_after.id == manual.id
    assert manual_after.smart_layout_rule_id is None

    assert smart_after is None