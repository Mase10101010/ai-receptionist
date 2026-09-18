import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_combination_rule import (
    TableCombinationRule,
    TableCombinationRuleMember,
    TableCombinationRuleStatus,
    build_table_combination_member_key,
)
from app.models.user import User

from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)


def test_member_key_is_order_independent():
    table_a = uuid.uuid4()
    table_b = uuid.uuid4()
    table_c = uuid.uuid4()

    first = build_table_combination_member_key(
        [table_a, table_b, table_c]
    )
    second = build_table_combination_member_key(
        [table_c, table_a, table_b]
    )

    assert first == second


def test_member_key_changes_for_different_member_set():
    table_a = uuid.uuid4()
    table_b = uuid.uuid4()
    table_c = uuid.uuid4()

    first = build_table_combination_member_key(
        [table_a, table_b]
    )
    second = build_table_combination_member_key(
        [table_a, table_c]
    )

    assert first != second


@pytest.mark.parametrize(
    "table_ids",
    [
        [],
        [uuid.uuid4()],
    ],
)
def test_member_key_requires_two_distinct_tables(table_ids):
    with pytest.raises(ValueError):
        build_table_combination_member_key(table_ids)


def test_member_key_rejects_duplicate_only_members():
    table_id = uuid.uuid4()

    with pytest.raises(ValueError):
        build_table_combination_member_key(
            [table_id, table_id]
        )


@pytest.mark.asyncio
async def test_rule_persists_members_and_status(db_session):
    user = User(
        email=f"smart-layout-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Smart Layout Test",
        slug=f"smart-layout-{uuid.uuid4()}",
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
            table_code=f"SMART-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    member_key = build_table_combination_member_key(
        [tables[0].id, tables[1].id]
    )

    rule = TableCombinationRule(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        member_key=member_key,
        status=TableCombinationRuleStatus.AUTO,
        members=[
            TableCombinationRuleMember(
                table_id=tables[0].id,
                sort_order=0,
            ),
            TableCombinationRuleMember(
                table_id=tables[1].id,
                sort_order=1,
            ),
        ],
    )

    db_session.add(rule)
    await db_session.flush()

    assert rule.id is not None
    assert rule.status == TableCombinationRuleStatus.AUTO
    assert rule.member_key == member_key
    assert len(rule.members) == 2
    assert {
        member.table_id
        for member in rule.members
    } == {
        tables[0].id,
        tables[1].id,
    }


@pytest.mark.asyncio
async def test_same_member_set_cannot_exist_twice_on_floor_plan(
    db_session,
):
    user = User(
        email=f"smart-layout-unique-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Smart Layout Unique Test",
        slug=f"smart-layout-unique-{uuid.uuid4()}",
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
            table_code=f"UNIQUE-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    key_forward = build_table_combination_member_key(
        [tables[0].id, tables[1].id]
    )
    key_reverse = build_table_combination_member_key(
        [tables[1].id, tables[0].id]
    )

    assert key_forward == key_reverse

    first_rule = TableCombinationRule(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        member_key=key_forward,
        status=TableCombinationRuleStatus.AUTO,
    )

    db_session.add(first_rule)
    await db_session.flush()

    duplicate_rule = TableCombinationRule(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        member_key=key_reverse,
        status=TableCombinationRuleStatus.BLOCKED,
    )

    db_session.add(duplicate_rule)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()

@pytest.mark.asyncio
async def test_repository_member_lookup_is_order_independent(
    db_session,
):
    user = User(
        email=f"repo-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Smart Layout Repository Test",
        slug=f"smart-layout-repo-{uuid.uuid4()}",
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
            table_code=f"REPO-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    repository = TableCombinationRuleRepository(
        db_session
    )

    created = await repository.create(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        table_ids=[
            tables[0].id,
            tables[1].id,
        ],
    )

    found = await repository.get_by_member_set(
        floor_plan_id=floor_plan.id,
        table_ids=[
            tables[1].id,
            tables[0].id,
        ],
    )

    assert found is not None
    assert found.id == created.id
    assert found.status == TableCombinationRuleStatus.AUTO
    assert [
        member.table_id
        for member in found.members
    ] == sorted(
        [tables[0].id, tables[1].id],
        key=str,
    )


@pytest.mark.asyncio
async def test_repository_preserves_manager_status(
    db_session,
):
    user = User(
        email=f"authority-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Smart Layout Authority Test",
        slug=f"smart-layout-authority-{uuid.uuid4()}",
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
            table_code=f"AUTH-{uuid.uuid4()}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        for index in range(1, 3)
    ]
    db_session.add_all(tables)
    await db_session.flush()

    repository = TableCombinationRuleRepository(
        db_session
    )

    rule = await repository.create(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        floor_plan_id=floor_plan.id,
        table_ids=[
            tables[0].id,
            tables[1].id,
        ],
    )

    confirmed = await repository.set_status(
        rule,
        TableCombinationRuleStatus.CONFIRMED,
    )

    assert (
        confirmed.status
        == TableCombinationRuleStatus.CONFIRMED
    )

    blocked = await repository.set_status(
        confirmed,
        TableCombinationRuleStatus.BLOCKED,
    )

    assert (
        blocked.status
        == TableCombinationRuleStatus.BLOCKED
    )

    rediscovered = await repository.get_by_member_set(
        floor_plan_id=floor_plan.id,
        table_ids=[
            tables[1].id,
            tables[0].id,
        ],
    )

    assert rediscovered is not None
    assert (
        rediscovered.status
        == TableCombinationRuleStatus.BLOCKED
    )