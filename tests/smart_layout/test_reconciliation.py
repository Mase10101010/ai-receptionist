import uuid

import pytest

from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_combination_rule import (
    TableCombinationRuleStatus,
)
from app.models.table_placement import TablePlacement
from app.models.user import User
from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.services.smart_layout.service import (
    SmartLayoutService,
)
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.services.smart_layout.materialization import (
    SmartLayoutMaterializationService,
)

from app.models.table_combination import TableCombination


@pytest.mark.asyncio
async def test_analysis_creates_auto_rule_for_adjacent_tables(
    db_session,
):
    user = User(
        email=f"reconcile-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Smart Layout Reconciliation",
        slug=f"reconcile-{uuid.uuid4()}",
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
            table_code=f"REC-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    placements = [
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=tables[0].id,
            x=0,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=tables[1].id,
            x=100,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
    ]

    db_session.add_all(placements)
    await db_session.flush()

    rule_repository = (
        TableCombinationRuleRepository(
            db_session
        )
    )

    service = SmartLayoutService(
        placement_repository=TablePlacementRepository(
            db_session
        ),
        rule_repository=rule_repository,
        floor_plan_repository=FloorPlanRepository(
            db_session
        ),
        service_area_repository=ServiceAreaRepository(
            db_session
        ),
        materialization_service=(
            SmartLayoutMaterializationService(
                combination_repository=(
                    TableCombinationRepository(
                        db_session
                    )
                ),
            )
        ),
    )

    result = await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = (
        await rule_repository.list_by_floor_plan(
            floor_plan.id
        )
    )

    assert result.discovered_count == 1
    assert result.created_auto_count == 1
    assert result.deleted_obsolete_auto_count == 0

    assert len(rules) == 1

    rule = rules[0]

    assert (
        rule.status
        == TableCombinationRuleStatus.AUTO
    )
    assert {
        member.table_id
        for member in rule.members
    } == {
        tables[0].id,
        tables[1].id,
    }

async def build_reconciliation_scenario(
    db_session,
):
    user = User(
        email=f"scenario-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Smart Layout Scenario",
        slug=f"scenario-{uuid.uuid4()}",
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
            table_code=f"SCENARIO-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    placements = [
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=tables[0].id,
            x=0,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=tables[1].id,
            x=100,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
    ]
    db_session.add_all(placements)
    await db_session.flush()

    rule_repository = TableCombinationRuleRepository(
        db_session
    )
    placement_repository = TablePlacementRepository(
        db_session
    )

    service = SmartLayoutService(
        placement_repository=placement_repository,
        rule_repository=rule_repository,
        floor_plan_repository=FloorPlanRepository(
            db_session
        ),
        service_area_repository=ServiceAreaRepository(
            db_session
        ),
        materialization_service=(
            SmartLayoutMaterializationService(
                combination_repository=(
                    TableCombinationRepository(
                        db_session
                    )
                ),
            )
        ),
    )

    return {
        "restaurant": restaurant,
        "area": area,
        "floor_plan": floor_plan,
        "tables": tables,
        "placements": placements,
        "rule_repository": rule_repository,
        "placement_repository": placement_repository,
        "service": service,
    }

@pytest.mark.asyncio
async def test_second_analysis_is_idempotent(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    service = scenario["service"]
    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]
    repository = scenario["rule_repository"]

    first = await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    second = await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await repository.list_by_floor_plan(
        floor_plan.id
    )

    assert first.created_auto_count == 1

    assert second.discovered_count == 1
    assert second.created_auto_count == 0
    assert second.preserved_auto_count == 1
    assert second.deleted_obsolete_auto_count == 0

    assert len(rules) == 1


@pytest.mark.asyncio
async def test_obsolete_auto_rule_is_deleted(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    service = scenario["service"]
    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]
    placements = scenario["placements"]
    placement_repository = scenario[
        "placement_repository"
    ]
    rule_repository = scenario[
        "rule_repository"
    ]

    await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    await placement_repository.update(
        placements[1],
        {
            "x": 400,
        },
    )

    result = await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await rule_repository.list_by_floor_plan(
        floor_plan.id
    )

    assert result.discovered_count == 0
    assert result.created_auto_count == 0
    assert result.deleted_obsolete_auto_count == 1

    assert rules == []


@pytest.mark.asyncio
async def test_confirmed_rule_survives_geometry_disappearance(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    service = scenario["service"]
    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]
    placements = scenario["placements"]
    placement_repository = scenario[
        "placement_repository"
    ]
    rule_repository = scenario[
        "rule_repository"
    ]

    await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await rule_repository.list_by_floor_plan(
        floor_plan.id
    )

    assert len(rules) == 1

    await rule_repository.set_status(
        rules[0],
        TableCombinationRuleStatus.CONFIRMED,
    )

    await placement_repository.update(
        placements[1],
        {
            "x": 400,
        },
    )

    result = await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    remaining = (
        await rule_repository.list_by_floor_plan(
            floor_plan.id
        )
    )

    assert result.discovered_count == 0
    assert result.deleted_obsolete_auto_count == 0
    assert result.preserved_confirmed_count == 1

    assert len(remaining) == 1
    assert (
        remaining[0].status
        == TableCombinationRuleStatus.CONFIRMED
    )


@pytest.mark.asyncio
async def test_blocked_rule_survives_rediscovery(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    service = scenario["service"]
    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]
    tables = scenario["tables"]
    rule_repository = scenario[
        "rule_repository"
    ]

    await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await rule_repository.list_by_floor_plan(
        floor_plan.id
    )

    assert len(rules) == 1

    blocked = await rule_repository.set_status(
        rules[0],
        TableCombinationRuleStatus.BLOCKED,
    )

    result = await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rediscovered = (
        await rule_repository.get_by_member_set(
            floor_plan_id=floor_plan.id,
            table_ids=[
                tables[1].id,
                tables[0].id,
            ],
        )
    )

    assert result.discovered_count == 1
    assert result.created_auto_count == 0
    assert result.preserved_blocked_count == 1

    assert rediscovered is not None
    assert rediscovered.id == blocked.id
    assert (
        rediscovered.status
        == TableCombinationRuleStatus.BLOCKED
    )

@pytest.mark.asyncio
async def test_analysis_rejects_service_area_from_other_restaurant(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    other_user = User(
        email=f"other-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(other_user)
    await db_session.flush()

    other_restaurant = Restaurant(
        owner_id=other_user.id,
        name="Other Restaurant",
        slug=f"other-{uuid.uuid4()}",
        opening_hour=0,
        closing_hour=23,
        number_of_tables=0,
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(other_restaurant)
    await db_session.flush()

    with pytest.raises(
        ValueError,
        match="Service area does not belong to restaurant",
    ):
        await scenario["service"].analyze_floor_plan(
            restaurant_id=other_restaurant.id,
            service_area_id=scenario["area"].id,
            floor_plan_id=scenario["floor_plan"].id,
        )


@pytest.mark.asyncio
async def test_analysis_rejects_floor_plan_from_other_area(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    other_area = ServiceArea(
        restaurant_id=scenario["restaurant"].id,
        name="Other Area",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(other_area)
    await db_session.flush()

    other_floor_plan = FloorPlan(
        service_area_id=other_area.id,
        name="Other Layout",
        is_default=True,
        is_active=True,
    )
    db_session.add(other_floor_plan)
    await db_session.flush()

    with pytest.raises(
        ValueError,
        match="Floor plan does not belong to service area",
    ):
        await scenario["service"].analyze_floor_plan(
            restaurant_id=scenario["restaurant"].id,
            service_area_id=scenario["area"].id,
            floor_plan_id=other_floor_plan.id,
        )

def smart_layout_key_for_table_ids(
    floor_plan_id,
    table_ids,
):
    member_key = "|".join(
        sorted(
            str(table_id)
            for table_id in table_ids
        )
    )

    return f"{floor_plan_id}:{member_key}"

@pytest.mark.asyncio
async def test_analysis_creates_derived_executable_combination_for_auto_join(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    result = await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    assert result.created_auto_count > 0

    rules = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    assert rules

    combination_repository = TableCombinationRepository(
        db_session
    )

    for rule in rules:
        if (
            rule.status
            != TableCombinationRuleStatus.AUTO
        ):
            continue

        rule_table_ids = {
            member.table_id
            for member in rule.members
        }

        assert len(rule_table_ids) == 2

        combination = (
            await combination_repository
            .get_by_smart_layout_key(
                smart_layout_key=(
                    smart_layout_key_for_table_ids(
                        scenario["floor_plan"].id,
                        rule_table_ids,
                    )
                ),
                restaurant_id=scenario[
                    "restaurant"
                ].id,
            )
        )

        assert combination is not None
        assert combination.is_active is True
        assert (
            combination.smart_layout_rule_id
            is None
        )

        combination_table_ids = {
            member.table_id
            for member in combination.members
        }

        assert (
            combination_table_ids
            == rule_table_ids
        )

@pytest.mark.asyncio
async def test_obsolete_auto_removes_join_and_derived_executable_combination(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    rules = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    auto_rules = [
        rule
        for rule in rules
        if rule.status
        == TableCombinationRuleStatus.AUTO
    ]

    assert auto_rules

    target_rule = auto_rules[0]

    target_table_ids = {
        member.table_id
        for member in target_rule.members
    }

    target_key = (
        smart_layout_key_for_table_ids(
            scenario["floor_plan"].id,
            target_table_ids,
        )
    )

    combination_repository = TableCombinationRepository(
        db_session
    )

    combination_before = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=target_key,
            restaurant_id=scenario[
                "restaurant"
            ].id,
        )
    )

    assert combination_before is not None

    placements = await scenario[
        "placement_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    target_placements = [
        placement
        for placement in placements
        if placement.table_id in target_table_ids
    ]

    assert target_placements

    for index, placement in enumerate(
        target_placements
    ):
        placement.x = 5000 + (index * 1000)
        placement.y = 5000 + (index * 1000)

    await db_session.flush()

    await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    rules_after = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    assert all(
        rule.id != target_rule.id
        for rule in rules_after
    )

    combination_after = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=target_key,
            restaurant_id=scenario[
                "restaurant"
            ].id,
        )
    )

    assert combination_after is None

@pytest.mark.asyncio
async def test_blocked_join_survives_analysis_but_is_excluded_from_execution(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    rules = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    auto_rules = [
        rule
        for rule in rules
        if rule.status
        == TableCombinationRuleStatus.AUTO
    ]

    assert auto_rules

    target_rule = auto_rules[0]

    target_table_ids = {
        member.table_id
        for member in target_rule.members
    }

    target_key = (
        smart_layout_key_for_table_ids(
            scenario["floor_plan"].id,
            target_table_ids,
        )
    )

    combination_repository = TableCombinationRepository(
        db_session
    )

    combination_before = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=target_key,
            restaurant_id=scenario[
                "restaurant"
            ].id,
        )
    )

    assert combination_before is not None

    target_rule = await scenario[
        "rule_repository"
    ].set_status(
        target_rule,
        TableCombinationRuleStatus.BLOCKED,
    )

    await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    rules_after = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    blocked_after = next(
        (
            rule
            for rule in rules_after
            if rule.id == target_rule.id
        ),
        None,
    )

    assert blocked_after is not None
    assert (
        blocked_after.status
        == TableCombinationRuleStatus.BLOCKED
    )

    combination_after = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=target_key,
            restaurant_id=scenario[
                "restaurant"
            ].id,
        )
    )

    assert combination_after is None

@pytest.mark.asyncio
async def test_confirmed_join_survives_geometry_disappearance_and_remains_executable(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    rules = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    auto_rules = [
        rule
        for rule in rules
        if rule.status
        == TableCombinationRuleStatus.AUTO
    ]

    assert auto_rules

    target_rule = auto_rules[0]

    target_table_ids = {
        member.table_id
        for member in target_rule.members
    }

    target_key = (
        smart_layout_key_for_table_ids(
            scenario["floor_plan"].id,
            target_table_ids,
        )
    )

    target_rule = await scenario[
        "rule_repository"
    ].set_status(
        target_rule,
        TableCombinationRuleStatus.CONFIRMED,
    )

    combination_repository = TableCombinationRepository(
        db_session
    )

    combination_before = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=target_key,
            restaurant_id=scenario[
                "restaurant"
            ].id,
        )
    )

    assert combination_before is not None

    combination_id = combination_before.id

    placements = await scenario[
        "placement_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    target_placements = [
        placement
        for placement in placements
        if placement.table_id in target_table_ids
    ]

    assert target_placements

    for index, placement in enumerate(
        target_placements
    ):
        placement.x = 5000 + (index * 1000)
        placement.y = 5000 + (index * 1000)

    await db_session.flush()

    await scenario["service"].analyze_floor_plan(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
    )

    rules_after = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        scenario["floor_plan"].id
    )

    confirmed_after = next(
        (
            rule
            for rule in rules_after
            if rule.id == target_rule.id
        ),
        None,
    )

    assert confirmed_after is not None
    assert (
        confirmed_after.status
        == TableCombinationRuleStatus.CONFIRMED
    )

    combination_after = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=target_key,
            restaurant_id=scenario[
                "restaurant"
            ].id,
        )
    )

    assert combination_after is not None

    # Stable executable identity survives geometry
    # disappearance because CONFIRMED remains an
    # effective physical join.
    assert combination_after.id == combination_id
    assert (
        combination_after.smart_layout_rule_id
        is None
    )

@pytest.mark.asyncio
async def test_join_chain_derives_executable_multi_table_combination(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]

    third_table = Table(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        table_code=f"CHAIN-{uuid.uuid4()}",
        table_number="3",
        seats=4,
        is_active=True,
    )
    db_session.add(third_table)
    await db_session.flush()

    third_placement = TablePlacement(
        floor_plan_id=floor_plan.id,
        table_id=third_table.id,
        x=200,
        y=0,
        width=80,
        height=80,
        rotation=0,
        is_visible=True,
    )
    db_session.add(third_placement)
    await db_session.flush()

    await scenario["service"].analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        floor_plan.id
    )

    assert len(rules) == 2
    assert all(
        len(rule.members) == 2
        for rule in rules
    )

    combination_repository = (
        TableCombinationRepository(
            db_session
        )
    )

    combinations = (
        await combination_repository
        .list_by_restaurant(
            restaurant_id=restaurant.id,
            service_area_id=area.id,
            include_inactive=True,
        )
    )

    derived = [
        combination
        for combination in combinations
        if combination.smart_layout_key is not None
    ]

    assert len(derived) == 3

    member_sets = {
        frozenset(
            member.table_id
            for member in combination.members
        )
        for combination in derived
    }

    assert member_sets == {
        frozenset({
            scenario["tables"][0].id,
            scenario["tables"][1].id,
        }),
        frozenset({
            scenario["tables"][1].id,
            third_table.id,
        }),
        frozenset({
            scenario["tables"][0].id,
            scenario["tables"][1].id,
            third_table.id,
        }),
    }

    assert all(
        combination.smart_layout_rule_id is None
        for combination in derived
    )


@pytest.mark.asyncio
async def test_blocked_join_is_excluded_from_derived_execution(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]

    third_table = Table(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        table_code=f"BLOCK-CHAIN-{uuid.uuid4()}",
        table_number="3",
        seats=4,
        is_active=True,
    )
    db_session.add(third_table)
    await db_session.flush()

    db_session.add(
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=third_table.id,
            x=200,
            y=0,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        )
    )
    await db_session.flush()

    await scenario["service"].analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await scenario[
        "rule_repository"
    ].list_by_floor_plan(
        floor_plan.id
    )

    middle_table_id = scenario["tables"][1].id

    bc_rule = next(
        rule
        for rule in rules
        if {
            member.table_id
            for member in rule.members
        } == {
            middle_table_id,
            third_table.id,
        }
    )

    await scenario[
        "rule_repository"
    ].set_status(
        bc_rule,
        TableCombinationRuleStatus.BLOCKED,
    )

    await scenario["service"].analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    combination_repository = (
        TableCombinationRepository(
            db_session
        )
    )

    combinations = (
        await combination_repository
        .list_by_restaurant(
            restaurant_id=restaurant.id,
            service_area_id=area.id,
            include_inactive=True,
        )
    )

    derived = [
        combination
        for combination in combinations
        if combination.smart_layout_key is not None
    ]

    assert len(derived) == 1

    assert {
        member.table_id
        for member in derived[0].members
    } == {
        scenario["tables"][0].id,
        scenario["tables"][1].id,
    }

@pytest.mark.asyncio
async def test_analyze_migrates_legacy_rule_materialization_to_scoped_derived_combination(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]
    service = scenario["service"]
    rule_repository = scenario["rule_repository"]

    combination_repository = TableCombinationRepository(
        db_session
    )

    # First analysis creates the physical join rules and
    # the new topology-derived executable combinations.
    await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    rules = await rule_repository.list_by_floor_plan(
        floor_plan.id
    )

    auto_rules = [
        rule
        for rule in rules
        if (
            rule.status
            == TableCombinationRuleStatus.AUTO
            and len(rule.members) == 2
        )
    ]

    assert auto_rules

    target_rule = auto_rules[0]

    target_table_ids = {
        member.table_id
        for member in target_rule.members
    }

    scoped_key = smart_layout_key_for_table_ids(
        floor_plan.id,
        target_table_ids,
    )

    # Remove the current derived executable so that we can
    # recreate the exact legacy M4 production state.
    current_derived = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=scoped_key,
            restaurant_id=restaurant.id,
        )
    )

    assert current_derived is not None

    await combination_repository.delete(
        current_derived
    )

    # Recreate a legacy M4 executable:
    # smart_layout_rule_id != NULL
    # smart_layout_key == NULL
    legacy_combination = TableCombination(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        smart_layout_rule_id=target_rule.id,
        smart_layout_key=None,
        name=f"Legacy Smart Layout {target_rule.id}",
        min_capacity=1,
        max_capacity=sum(
            member.table.seats
            for member in target_rule.members
        ),
        setup_minutes=0,
        is_active=True,
    )

    legacy_combination = (
        await combination_repository.create(
            legacy_combination
        )
    )

    legacy_combination = (
        await combination_repository.replace_members(
            combination=legacy_combination,
            table_ids=sorted(
                target_table_ids,
                key=str,
            ),
        )
    )

    legacy_combination_id = legacy_combination.id

    # Also create a manual combination.
    # Migration cleanup must never touch it.
    manual_combination = TableCombination(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        name=f"Manual Control {uuid.uuid4()}",
        min_capacity=1,
        max_capacity=sum(
            member.table.seats
            for member in target_rule.members
        ),
        setup_minutes=0,
        is_active=True,
    )

    manual_combination = (
        await combination_repository.create(
            manual_combination
        )
    )

    manual_combination = (
        await combination_repository.replace_members(
            combination=manual_combination,
            table_ids=sorted(
                target_table_ids,
                key=str,
            ),
        )
    )

    manual_combination_id = manual_combination.id

    await db_session.flush()

    # Sanity check: we are now simulating the old production
    # materialization state.
    legacy_before = (
        await combination_repository
        .get_by_smart_layout_rule_id(
            smart_layout_rule_id=target_rule.id,
            restaurant_id=restaurant.id,
        )
    )

    assert legacy_before is not None
    assert legacy_before.id == legacy_combination_id
    assert legacy_before.smart_layout_key is None

    # Analyze again using the new topology pipeline.
    await service.analyze_floor_plan(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    # The physical authority rule must survive.
    rule_after = await rule_repository.get_by_id(
        rule_id=target_rule.id,
        restaurant_id=restaurant.id,
    )

    assert rule_after is not None
    assert (
        rule_after.status
        == TableCombinationRuleStatus.AUTO
    )

    # Legacy M4 executable must be gone.
    legacy_after = (
        await combination_repository
        .get_by_smart_layout_rule_id(
            smart_layout_rule_id=target_rule.id,
            restaurant_id=restaurant.id,
        )
    )

    assert legacy_after is None

    # New Floor-Plan-scoped derived executable must exist.
    derived_after = (
        await combination_repository
        .get_by_smart_layout_key(
            smart_layout_key=scoped_key,
            restaurant_id=restaurant.id,
        )
    )

    assert derived_after is not None
    assert derived_after.id != legacy_combination_id
    assert derived_after.smart_layout_rule_id is None
    assert derived_after.smart_layout_key == scoped_key

    derived_table_ids = {
        member.table_id
        for member in derived_after.members
    }

    assert derived_table_ids == target_table_ids

    # Manual manager-created combination must remain untouched.
    manual_after = await combination_repository.get_by_id(
        combination_id=manual_combination_id,
        restaurant_id=restaurant.id,
    )

    assert manual_after is not None
    assert manual_after.id == manual_combination_id
    assert manual_after.smart_layout_rule_id is None
    assert manual_after.smart_layout_key is None

@pytest.mark.asyncio
async def test_placement_repository_eager_loads_table_relationship(
    db_session,
):
    scenario = await build_reconciliation_scenario(
        db_session
    )

    floor_plan_id = scenario["floor_plan"].id
    expected_table_ids = {
        table.id
        for table in scenario["tables"]
    }

    # Simulate a fresh request/session state.
    #
    # Existing reconciliation tests create Table and
    # TablePlacement objects in the same SQLAlchemy session,
    # which can leave Table instances in the identity map and
    # hide an accidental lazy load.
    db_session.expire_all()

    repository = TablePlacementRepository(
        db_session
    )

    placements = await repository.list_by_floor_plan(
        floor_plan_id
    )

    assert len(placements) == 2

    # This access must not trigger async lazy loading.
    # list_by_floor_plan() owns the contract of returning
    # placements with TablePlacement.table already loaded.
    loaded_table_ids = {
        placement.table.id
        for placement in placements
    }

    assert loaded_table_ids == expected_table_ids