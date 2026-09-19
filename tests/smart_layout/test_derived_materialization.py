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
from app.models.user import User
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.services.smart_layout.derived_materialization import (
    SmartLayoutDerivedMaterializationService,
)


async def build_derived_materialization_scenario(
    db_session,
):
    user = User(
        email=f"derived-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Derived Materialization Restaurant",
        slug=f"derived-{uuid.uuid4()}",
        opening_hour=0,
        closing_hour=23,
        number_of_tables=3,
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
        name=f"Derived Plan {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    tables = [
        Table(
            restaurant_id=restaurant.id,
            service_area_id=area.id,
            table_code=f"DER-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 4)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    repository = TableCombinationRepository(
        db_session
    )

    service = SmartLayoutDerivedMaterializationService(
        combination_repository=repository,
    )

    return {
        "restaurant": restaurant,
        "area": area,
        "floor_plan": floor_plan,
        "tables": tables,
        "repository": repository,
        "service": service,
    }


def combination_key(
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
async def test_sync_creates_all_derived_combinations(
    db_session,
):
    scenario = await build_derived_materialization_scenario(
        db_session
    )

    tables = scenario["tables"]

    ab = frozenset({
        tables[0].id,
        tables[1].id,
    })
    bc = frozenset({
        tables[1].id,
        tables[2].id,
    })
    abc = frozenset({
        tables[0].id,
        tables[1].id,
        tables[2].id,
    })

    await scenario["service"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=[ab, bc, abc],
        tables_by_id={
            table.id: table
            for table in tables
        },
    )

    combinations = await scenario[
        "repository"
    ].list_by_restaurant(
        restaurant_id=scenario["restaurant"].id,
        include_inactive=True,
    )

    derived = [
        combination
        for combination in combinations
        if combination.smart_layout_key is not None
    ]

    assert len(derived) == 3

    assert {
        combination.smart_layout_key
        for combination in derived
    } == {
        combination_key(
            scenario["floor_plan"].id,
            ab,
        ),
        combination_key(
            scenario["floor_plan"].id,
            bc,
        ),
        combination_key(
            scenario["floor_plan"].id,
            abc,
        ),
    }

    assert all(
        combination.smart_layout_rule_id is None
        for combination in derived
    )


@pytest.mark.asyncio
async def test_sync_preserves_stable_combination_ids(
    db_session,
):
    scenario = await build_derived_materialization_scenario(
        db_session
    )

    tables = scenario["tables"]

    derived_sets = [
        frozenset({
            tables[0].id,
            tables[1].id,
        }),
        frozenset({
            tables[1].id,
            tables[2].id,
        }),
        frozenset({
            tables[0].id,
            tables[1].id,
            tables[2].id,
        }),
    ]

    await scenario["service"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=derived_sets,
        tables_by_id={
            table.id: table
            for table in tables
        },
    )

    first = await scenario[
        "repository"
    ].list_by_restaurant(
        restaurant_id=scenario["restaurant"].id,
        include_inactive=True,
    )

    first_ids = {
        combination.smart_layout_key: combination.id
        for combination in first
        if combination.smart_layout_key is not None
    }

    await scenario["service"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=derived_sets,
        tables_by_id={
            table.id: table
            for table in tables
        },
    )

    second = await scenario[
        "repository"
    ].list_by_restaurant(
        restaurant_id=scenario["restaurant"].id,
        include_inactive=True,
    )

    second_ids = {
        combination.smart_layout_key: combination.id
        for combination in second
        if combination.smart_layout_key is not None
    }

    assert second_ids == first_ids
    assert len(second_ids) == 3


@pytest.mark.asyncio
async def test_sync_removes_only_obsolete_derived_combinations(
    db_session,
):
    scenario = await build_derived_materialization_scenario(
        db_session
    )

    tables = scenario["tables"]

    ab = frozenset({
        tables[0].id,
        tables[1].id,
    })
    bc = frozenset({
        tables[1].id,
        tables[2].id,
    })
    abc = frozenset({
        tables[0].id,
        tables[1].id,
        tables[2].id,
    })

    tables_by_id = {
        table.id: table
        for table in tables
    }

    await scenario["service"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=[ab, bc, abc],
        tables_by_id=tables_by_id,
    )

    ab_before = (
        await scenario[
            "repository"
        ].get_by_smart_layout_key(
            smart_layout_key=combination_key(
                scenario["floor_plan"].id,
                ab,
            ),
            restaurant_id=scenario["restaurant"].id,
        )
    )

    assert ab_before is not None
    ab_id = ab_before.id

    await scenario["service"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=[ab],
        tables_by_id=tables_by_id,
    )

    combinations = await scenario[
        "repository"
    ].list_by_restaurant(
        restaurant_id=scenario["restaurant"].id,
        include_inactive=True,
    )

    derived = [
        combination
        for combination in combinations
        if combination.smart_layout_key is not None
    ]

    assert len(derived) == 1
    assert derived[0].id == ab_id
    assert (
        derived[0].smart_layout_key
        == combination_key(
            scenario["floor_plan"].id,
            ab,
        )
    )


@pytest.mark.asyncio
async def test_sync_never_deletes_manual_combination(
    db_session,
):
    scenario = await build_derived_materialization_scenario(
        db_session
    )

    tables = scenario["tables"]
    repository = scenario["repository"]

    manual = TableCombination(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        name=f"Manual {uuid.uuid4()}",
        min_capacity=1,
        max_capacity=8,
        setup_minutes=0,
        is_active=True,
        members=[
            TableCombinationMember(
                table_id=tables[0].id,
                sort_order=0,
            ),
            TableCombinationMember(
                table_id=tables[1].id,
                sort_order=1,
            ),
        ],
    )

    manual = await repository.create(manual)

    await scenario["service"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=[],
        tables_by_id={
            table.id: table
            for table in tables
        },
    )

    manual_after = await repository.get_by_id(
        combination_id=manual.id,
        restaurant_id=scenario["restaurant"].id,
    )

    assert manual_after is not None
    assert manual_after.id == manual.id
    assert manual_after.smart_layout_key is None
    assert manual_after.smart_layout_rule_id is None


@pytest.mark.asyncio
async def test_sync_isolated_between_floor_plans(
    db_session,
):
    scenario = await build_derived_materialization_scenario(
        db_session
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    tables = scenario["tables"]
    service = scenario["service"]
    repository = scenario["repository"]

    floor_plan_a = FloorPlan(
        service_area_id=area.id,
        name=f"Plan A {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=1,
        is_default=False,
        is_active=True,
    )

    floor_plan_b = FloorPlan(
        service_area_id=area.id,
        name=f"Plan B {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=2,
        is_default=False,
        is_active=True,
    )

    db_session.add_all([
        floor_plan_a,
        floor_plan_b,
    ])
    await db_session.flush()

    ab = frozenset({
        tables[0].id,
        tables[1].id,
    })

    bc = frozenset({
        tables[1].id,
        tables[2].id,
    })

    tables_by_id = {
        table.id: table
        for table in tables
    }

    # Floor Plan A owns AB.
    await service.sync(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan_a.id,
        derived_table_sets=[ab],
        tables_by_id=tables_by_id,
    )

    # Floor Plan B owns BC.
    await service.sync(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan_b.id,
        derived_table_sets=[bc],
        tables_by_id=tables_by_id,
    )

    key_a = service._build_key(
        floor_plan_id=floor_plan_a.id,
        table_ids=ab,
    )
    key_b = service._build_key(
        floor_plan_id=floor_plan_b.id,
        table_ids=bc,
    )

    combination_a = (
        await repository.get_by_smart_layout_key(
            smart_layout_key=key_a,
            restaurant_id=restaurant.id,
        )
    )
    combination_b = (
        await repository.get_by_smart_layout_key(
            smart_layout_key=key_b,
            restaurant_id=restaurant.id,
        )
    )

    assert combination_a is not None
    assert combination_b is not None

    combination_a_id = combination_a.id
    combination_b_id = combination_b.id

    # Re-sync A only.
    # B must remain completely untouched.
    await service.sync(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan_a.id,
        derived_table_sets=[ab],
        tables_by_id=tables_by_id,
    )

    combination_a_after = (
        await repository.get_by_smart_layout_key(
            smart_layout_key=key_a,
            restaurant_id=restaurant.id,
        )
    )
    combination_b_after = (
        await repository.get_by_smart_layout_key(
            smart_layout_key=key_b,
            restaurant_id=restaurant.id,
        )
    )

    assert combination_a_after is not None
    assert combination_b_after is not None

    assert combination_a_after.id == combination_a_id
    assert combination_b_after.id == combination_b_id

@pytest.mark.asyncio
async def test_sync_uses_short_human_readable_name(
    db_session,
):
    scenario = await build_derived_materialization_scenario(
        db_session
    )

    restaurant = scenario["restaurant"]
    area = scenario["area"]
    floor_plan = scenario["floor_plan"]
    repository = scenario["repository"]
    service = scenario["service"]

    tables = scenario["tables"]

    fourth_table = Table(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        table_code=f"DER-{uuid.uuid4()}",
        table_number="4",
        seats=4,
        is_active=True,
    )

    db_session.add(fourth_table)
    await db_session.flush()

    all_tables = [
        *tables,
        fourth_table,
    ]

    four_table_set = frozenset(
        table.id
        for table in all_tables
    )

    await service.sync(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        derived_table_sets=[four_table_set],
        tables_by_id={
            table.id: table
            for table in all_tables
        },
    )

    smart_layout_key = combination_key(
        floor_plan.id,
        four_table_set,
    )

    combination = (
        await repository.get_by_smart_layout_key(
            smart_layout_key=smart_layout_key,
            restaurant_id=restaurant.id,
        )
    )

    assert combination is not None

    # Technical identity remains complete and stable.
    assert combination.smart_layout_key == smart_layout_key

    # Human-readable name must never mirror the long UUID key.
    assert combination.name == "Smart Layout 1 + 2 + 3 + 4"
    assert len(combination.name) <= 100
    assert str(floor_plan.id) not in combination.name