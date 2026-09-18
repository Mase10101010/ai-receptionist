from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.main import app
from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_combination import TableCombination
from app.models.table_combination_rule import TableCombinationRule
from app.models.table_placement import TablePlacement
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _get_workspace(
    db_session: AsyncSession,
) -> tuple[User, Restaurant, ServiceArea, list[Table]]:
    user = (
        await db_session.execute(
            select(User).order_by(User.email)
        )
    ).scalars().first()
    assert user is not None

    restaurant = (
        await db_session.execute(
            select(Restaurant).where(Restaurant.owner_id == user.id)
        )
    ).scalars().one()

    area = (
        await db_session.execute(
            select(ServiceArea).where(
                ServiceArea.restaurant_id == restaurant.id
            )
        )
    ).scalars().one()

    tables = list(
        (
            await db_session.execute(
                select(Table)
                .where(Table.restaurant_id == restaurant.id)
                .order_by(Table.table_number)
            )
        ).scalars().all()
    )

    assert len(tables) >= 2

    return user, restaurant, area, tables


async def _create_floor_plan_with_adjacent_tables(
    db_session: AsyncSession,
    *,
    area: ServiceArea,
    tables: list[Table],
) -> FloorPlan:
    floor_plan = FloorPlan(
        service_area_id=area.id,
        name=f"Smart Layout Test {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    placements = [
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=tables[0].id,
            x=100,
            y=100,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
        TablePlacement(
            floor_plan_id=floor_plan.id,
            table_id=tables[1].id,
            x=190,
            y=100,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        ),
    ]

    db_session.add_all(placements)
    await db_session.flush()

    return floor_plan


def _analyze_url(
    *,
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
) -> str:
    return (
        f"/api/v1/restaurants/{restaurant_id}"
        f"/service-areas/{area_id}"
        f"/floor-plans/{floor_plan_id}"
        "/smart-layout/analyze"
    )


async def _count_rules(
    db_session: AsyncSession,
) -> int:
    return (
        await db_session.execute(
            select(func.count()).select_from(TableCombinationRule)
        )
    ).scalar_one()


async def _count_smart_combinations(
    db_session: AsyncSession,
) -> int:
    return (
        await db_session.execute(
            select(func.count())
            .select_from(TableCombination)
            .where(
                TableCombination.smart_layout_rule_id.is_not(None)
            )
        )
    ).scalar_one()


async def test_analyze_creates_and_persists_smart_layout(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=floor_plan.id,
        )
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["discovered_count"] >= 1
    assert payload["created_auto_count"] >= 1

    assert await _count_rules(db_session) >= 1
    assert await _count_smart_combinations(db_session) >= 1


async def test_analyze_foreign_owner_returns_404_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    foreign_user = User(
        email=f"foreign-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(foreign_user)
    await db_session.flush()

    async def _override_foreign_user():
        return foreign_user

    original_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _override_foreign_user

    try:
        response = await client.post(
            _analyze_url(
                restaurant_id=restaurant.id,
                area_id=area.id,
                floor_plan_id=floor_plan.id,
            )
        )
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original_override

    assert response.status_code == 404
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0


async def test_analyze_wrong_service_area_returns_404_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=uuid.uuid4(),
            floor_plan_id=floor_plan.id,
        )
    )

    assert response.status_code == 404
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0


async def test_analyze_wrong_floor_plan_returns_404_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, _ = await _get_workspace(db_session)

    response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=uuid.uuid4(),
        )
    )

    assert response.status_code == 404
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0


async def test_analyze_inactive_subscription_returns_403_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    restaurant.subscription_status = "inactive"
    await db_session.flush()

    response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=floor_plan.id,
        )
    )

    assert response.status_code == 403
    assert await _count_rules(db_session) == 0
    assert await _count_smart_combinations(db_session) == 0

async def test_list_rules_returns_analyzed_rules(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    analyze_url = _analyze_url(
        restaurant_id=restaurant.id,
        area_id=area.id,
        floor_plan_id=floor_plan.id,
    )

    analyze_response = await client.post(analyze_url)
    assert analyze_response.status_code == 200, analyze_response.text

    rules_url = (
        f"/api/v1/restaurants/{restaurant.id}"
        f"/service-areas/{area.id}"
        f"/floor-plans/{floor_plan.id}"
        "/smart-layout/rules"
    )

    response = await client.get(rules_url)

    assert response.status_code == 200, response.text

    payload = response.json()

    assert len(payload) >= 1

    first_rule = payload[0]

    assert first_rule["restaurant_id"] == str(restaurant.id)
    assert first_rule["service_area_id"] == str(area.id)
    assert first_rule["floor_plan_id"] == str(floor_plan.id)
    assert first_rule["status"] == "auto"
    assert first_rule["member_key"]

    assert len(first_rule["members"]) >= 2

    sort_orders = [
        member["sort_order"]
        for member in first_rule["members"]
    ]

    assert sort_orders == sorted(sort_orders)


async def test_list_rules_empty_floor_plan_returns_empty_list(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    rules_url = (
        f"/api/v1/restaurants/{restaurant.id}"
        f"/service-areas/{area.id}"
        f"/floor-plans/{floor_plan.id}"
        "/smart-layout/rules"
    )

    response = await client.get(rules_url)

    assert response.status_code == 200, response.text
    assert response.json() == []


async def test_list_rules_foreign_owner_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    foreign_user = User(
        email=f"foreign-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(foreign_user)
    await db_session.flush()

    async def _override_foreign_user():
        return foreign_user

    original_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _override_foreign_user

    try:
        response = await client.get(
            (
                f"/api/v1/restaurants/{restaurant.id}"
                f"/service-areas/{area.id}"
                f"/floor-plans/{floor_plan.id}"
                "/smart-layout/rules"
            )
        )
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original_override

    assert response.status_code == 404


async def test_list_rules_wrong_area_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    response = await client.get(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{uuid.uuid4()}"
            f"/floor-plans/{floor_plan.id}"
            "/smart-layout/rules"
        )
    )

    assert response.status_code == 404


async def test_list_rules_wrong_floor_plan_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, _ = await _get_workspace(db_session)

    response = await client.get(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{area.id}"
            f"/floor-plans/{uuid.uuid4()}"
            "/smart-layout/rules"
        )
    )

    assert response.status_code == 404


async def test_list_rules_inactive_subscription_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    restaurant.subscription_status = "inactive"
    await db_session.flush()

    response = await client.get(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{area.id}"
            f"/floor-plans/{floor_plan.id}"
            "/smart-layout/rules"
        )
    )

    assert response.status_code == 403

async def test_manager_control_full_authority_cycle(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    base_url = (
        f"/api/v1/restaurants/{restaurant.id}"
        f"/service-areas/{area.id}"
        f"/floor-plans/{floor_plan.id}"
        "/smart-layout"
    )

    # ---------------------------------------------------------
    # 1. ANALYZE -> AUTO rule + executable combination
    # ---------------------------------------------------------

    response = await client.post(f"{base_url}/analyze")
    assert response.status_code == 200, response.text

    rules_response = await client.get(f"{base_url}/rules")
    assert rules_response.status_code == 200, rules_response.text

    rules = rules_response.json()
    assert len(rules) >= 1

    rule = rules[0]
    rule_id = rule["id"]

    assert rule["status"] == "auto"

    smart_combination_count = await _count_smart_combinations(
        db_session
    )
    assert smart_combination_count >= 1

    # ---------------------------------------------------------
    # 2. AUTO -> BLOCKED
    # Rule survives, executable disappears immediately.
    # ---------------------------------------------------------

    response = await client.patch(
        f"{base_url}/rules/{rule_id}",
        json={"status": "blocked"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "blocked"

    persisted_rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.id == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert persisted_rule is not None
    assert persisted_rule.status.value == "blocked"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id
                == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert combination is None

    # ---------------------------------------------------------
    # 3. Analyze again while BLOCKED.
    # BLOCKED must override automatic discovery.
    # ---------------------------------------------------------

    response = await client.post(f"{base_url}/analyze")
    assert response.status_code == 200, response.text

    persisted_rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.id == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert persisted_rule is not None
    assert persisted_rule.status.value == "blocked"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id
                == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert combination is None

    # ---------------------------------------------------------
    # 4. BLOCKED -> CONFIRMED
    # Executable must return immediately.
    # ---------------------------------------------------------

    response = await client.patch(
        f"{base_url}/rules/{rule_id}",
        json={"status": "confirmed"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "confirmed"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id
                == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert combination is not None

    # ---------------------------------------------------------
    # 5. Destroy geometric adjacency.
    # CONFIRMED must survive Analyze.
    # ---------------------------------------------------------

    placement = (
        await db_session.execute(
            select(TablePlacement).where(
                TablePlacement.floor_plan_id == floor_plan.id,
                TablePlacement.table_id == tables[1].id,
            )
        )
    ).scalar_one()

    placement.x = 900
    placement.y = 600
    await db_session.flush()

    response = await client.post(f"{base_url}/analyze")
    assert response.status_code == 200, response.text

    persisted_rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.id == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert persisted_rule is not None
    assert persisted_rule.status.value == "confirmed"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id
                == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert combination is not None

    # ---------------------------------------------------------
    # 6. CONFIRMED -> AUTO while geometry no longer supports it.
    #
    # AUTO returns authority to current geometry.
    # Reconciliation must therefore remove both executable
    # combination and obsolete AUTO rule immediately.
    # ---------------------------------------------------------

    response = await client.patch(
        f"{base_url}/rules/{rule_id}",
        json={"status": "auto"},
    )

    assert response.status_code == 200, response.text
    assert response.json() is None

    persisted_rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.id == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert persisted_rule is None

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id
                == uuid.UUID(rule_id)
            )
        )
    ).scalar_one_or_none()

    assert combination is None


async def test_patch_unknown_rule_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    response = await client.patch(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{area.id}"
            f"/floor-plans/{floor_plan.id}"
            f"/smart-layout/rules/{uuid.uuid4()}"
        ),
        json={"status": "blocked"},
    )

    assert response.status_code == 404


async def test_patch_invalid_status_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=floor_plan.id,
        )
    )
    assert response.status_code == 200, response.text

    rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.floor_plan_id == floor_plan.id
            )
        )
    ).scalars().first()

    assert rule is not None

    response = await client.patch(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{area.id}"
            f"/floor-plans/{floor_plan.id}"
            f"/smart-layout/rules/{rule.id}"
        ),
        json={"status": "whatever"},
    )

    assert response.status_code == 422

async def test_patch_foreign_owner_returns_404_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    analyze_response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=floor_plan.id,
        )
    )
    assert analyze_response.status_code == 200, analyze_response.text

    rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.floor_plan_id == floor_plan.id
            )
        )
    ).scalars().first()

    assert rule is not None
    assert rule.status.value == "auto"

    foreign_user = User(
        email=f"foreign-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(foreign_user)
    await db_session.flush()

    async def _override_foreign_user():
        return foreign_user

    original_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _override_foreign_user

    try:
        response = await client.patch(
            (
                f"/api/v1/restaurants/{restaurant.id}"
                f"/service-areas/{area.id}"
                f"/floor-plans/{floor_plan.id}"
                f"/smart-layout/rules/{rule.id}"
            ),
            json={"status": "blocked"},
        )
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original_override

    assert response.status_code == 404

    await db_session.refresh(rule)
    assert rule.status.value == "auto"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id == rule.id
            )
        )
    ).scalar_one_or_none()

    assert combination is not None


async def test_patch_wrong_floor_plan_returns_404_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    analyze_response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=floor_plan.id,
        )
    )
    assert analyze_response.status_code == 200, analyze_response.text

    rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.floor_plan_id == floor_plan.id
            )
        )
    ).scalars().first()

    assert rule is not None
    assert rule.status.value == "auto"

    response = await client.patch(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{area.id}"
            f"/floor-plans/{uuid.uuid4()}"
            f"/smart-layout/rules/{rule.id}"
        ),
        json={"status": "blocked"},
    )

    assert response.status_code == 404

    await db_session.refresh(rule)
    assert rule.status.value == "auto"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id == rule.id
            )
        )
    ).scalar_one_or_none()

    assert combination is not None


async def test_patch_inactive_subscription_returns_403_without_mutation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, restaurant, area, tables = await _get_workspace(db_session)

    floor_plan = await _create_floor_plan_with_adjacent_tables(
        db_session,
        area=area,
        tables=tables,
    )

    analyze_response = await client.post(
        _analyze_url(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=floor_plan.id,
        )
    )
    assert analyze_response.status_code == 200, analyze_response.text

    rule = (
        await db_session.execute(
            select(TableCombinationRule).where(
                TableCombinationRule.floor_plan_id == floor_plan.id
            )
        )
    ).scalars().first()

    assert rule is not None
    assert rule.status.value == "auto"

    restaurant.subscription_status = "inactive"
    await db_session.flush()

    response = await client.patch(
        (
            f"/api/v1/restaurants/{restaurant.id}"
            f"/service-areas/{area.id}"
            f"/floor-plans/{floor_plan.id}"
            f"/smart-layout/rules/{rule.id}"
        ),
        json={"status": "blocked"},
    )

    assert response.status_code == 403

    await db_session.refresh(rule)
    assert rule.status.value == "auto"

    combination = (
        await db_session.execute(
            select(TableCombination).where(
                TableCombination.smart_layout_rule_id == rule.id
            )
        )
    ).scalar_one_or_none()

    assert combination is not None