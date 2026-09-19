import uuid

import pytest

from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.services.smart_layout.derivation import (
    derive_table_combinations,
)
from app.services.smart_layout.derived_materialization import (
    SmartLayoutDerivedMaterializationService,
)


async def build_derived_pipeline_scenario(
    db_session,
):
    user = User(
        email=f"pipeline-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Derived Pipeline Restaurant",
        slug=f"pipeline-{uuid.uuid4()}",
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
        name=f"Pipeline Plan {uuid.uuid4()}",
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
            table_code=f"PIPE-{uuid.uuid4()}",
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

    materializer = (
        SmartLayoutDerivedMaterializationService(
            combination_repository=repository,
        )
    )

    return {
        "restaurant": restaurant,
        "area": area,
        "floor_plan": floor_plan,
        "tables": tables,
        "repository": repository,
        "materializer": materializer,
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
async def test_physical_join_chain_derives_and_materializes_combinations(
    db_session,
):
    scenario = await build_derived_pipeline_scenario(
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

    physical_joins = [
        ab,
        bc,
    ]

    derived = derive_table_combinations(
        physical_joins
    )

    assert set(derived) == {
        ab,
        bc,
        abc,
    }

    await scenario["materializer"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=derived,
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

    smart = [
        combination
        for combination in combinations
        if combination.smart_layout_key is not None
    ]

    assert len(smart) == 3

    assert {
        combination.smart_layout_key
        for combination in smart
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


@pytest.mark.asyncio
async def test_removing_join_reconciles_derived_combinations(
    db_session,
):
    scenario = await build_derived_pipeline_scenario(
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

    tables_by_id = {
        table.id: table
        for table in tables
    }

    initial = derive_table_combinations(
        [ab, bc]
    )

    await scenario["materializer"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=initial,
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

    after_block = derive_table_combinations(
        [ab]
    )

    await scenario["materializer"].sync(
        restaurant_id=scenario["restaurant"].id,
        service_area_id=scenario["area"].id,
        floor_plan_id=scenario["floor_plan"].id,
        derived_table_sets=after_block,
        tables_by_id=tables_by_id,
    )

    combinations = await scenario[
        "repository"
    ].list_by_restaurant(
        restaurant_id=scenario["restaurant"].id,
        include_inactive=True,
    )

    smart = [
        combination
        for combination in combinations
        if combination.smart_layout_key is not None
    ]

    assert len(smart) == 1
    assert smart[0].id == ab_id
    assert (
        smart[0].smart_layout_key
        == combination_key(
            scenario["floor_plan"].id,
            ab,
        )
    )