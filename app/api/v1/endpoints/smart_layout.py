import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.schemas.smart_layout import (
    SmartLayoutAnalysisResponse,
    SmartLayoutRuleMemberResponse,
    SmartLayoutRuleResponse,
    SmartLayoutRuleStatusUpdate,
)
from app.services.smart_layout.api_service import (
    SmartLayoutApiService,
)
from app.services.smart_layout.materialization import (
    SmartLayoutMaterializationService,
)
from app.services.smart_layout.service import (
    SmartLayoutService,
)


router = APIRouter(
    prefix=(
        "/restaurants/{restaurant_id}"
        "/service-areas/{area_id}"
        "/floor-plans/{floor_plan_id}"
        "/smart-layout"
    ),
    tags=["smart layout"],
)


def get_smart_layout_api_service(
    db: AsyncSession = Depends(get_db),
) -> SmartLayoutApiService:
    floor_plan_repository = FloorPlanRepository(db)
    service_area_repository = ServiceAreaRepository(db)
    rule_repository = TableCombinationRuleRepository(db)

    materialization_service = SmartLayoutMaterializationService(
        combination_repository=TableCombinationRepository(db),
    )

    smart_layout_service = SmartLayoutService(
        placement_repository=TablePlacementRepository(db),
        rule_repository=rule_repository,
        floor_plan_repository=floor_plan_repository,
        service_area_repository=service_area_repository,
        materialization_service=materialization_service,
    )

    return SmartLayoutApiService(
        smart_layout_service=smart_layout_service,
        restaurant_repository=RestaurantRepository(db),
        service_area_repository=service_area_repository,
        floor_plan_repository=floor_plan_repository,
        rule_repository=rule_repository,
    )


@router.post(
    "/analyze",
    response_model=SmartLayoutAnalysisResponse,
)
async def analyze_smart_layout(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: SmartLayoutApiService = Depends(
        get_smart_layout_api_service,
    ),
) -> SmartLayoutAnalysisResponse:
    result = await service.analyze_floor_plan(
        restaurant_id=restaurant_id,
        area_id=area_id,
        floor_plan_id=floor_plan_id,
        owner_id=current_user.id,
    )

    await service.rule_repository.db.commit()

    return SmartLayoutAnalysisResponse(
        discovered_count=result.discovered_count,
        created_auto_count=result.created_auto_count,
        preserved_auto_count=result.preserved_auto_count,
        preserved_confirmed_count=result.preserved_confirmed_count,
        preserved_blocked_count=result.preserved_blocked_count,
        deleted_obsolete_auto_count=(
            result.deleted_obsolete_auto_count
        ),
    )


@router.get(
    "/rules",
    response_model=list[SmartLayoutRuleResponse],
)
async def list_smart_layout_rules(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: SmartLayoutApiService = Depends(
        get_smart_layout_api_service,
    ),
) -> list[SmartLayoutRuleResponse]:
    rules = await service.list_rules(
        restaurant_id=restaurant_id,
        area_id=area_id,
        floor_plan_id=floor_plan_id,
        owner_id=current_user.id,
    )

    return [
        SmartLayoutRuleResponse(
            id=rule.id,
            restaurant_id=rule.restaurant_id,
            service_area_id=rule.service_area_id,
            floor_plan_id=rule.floor_plan_id,
            member_key=rule.member_key,
            status=rule.status,
            members=[
                SmartLayoutRuleMemberResponse(
                    table_id=member.table_id,
                    sort_order=member.sort_order,
                )
                for member in sorted(
                    rule.members,
                    key=lambda member: member.sort_order,
                )
            ],
        )
        for rule in rules
    ]
def serialize_rule(rule) -> SmartLayoutRuleResponse:
    return SmartLayoutRuleResponse(
        id=rule.id,
        restaurant_id=rule.restaurant_id,
        service_area_id=rule.service_area_id,
        floor_plan_id=rule.floor_plan_id,
        member_key=rule.member_key,
        status=rule.status,
        members=[
            SmartLayoutRuleMemberResponse(
                table_id=member.table_id,
                sort_order=member.sort_order,
            )
            for member in sorted(
                rule.members,
                key=lambda member: member.sort_order,
            )
        ],
    )

@router.patch(
    "/rules/{rule_id}",
    response_model=SmartLayoutRuleResponse | None,
)
async def update_smart_layout_rule_status(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    rule_id: uuid.UUID,
    payload: SmartLayoutRuleStatusUpdate,
    current_user: CurrentUserDep,
    service: SmartLayoutApiService = Depends(
        get_smart_layout_api_service,
    ),
) -> SmartLayoutRuleResponse | None:
    rule = await service.update_rule_status(
        restaurant_id=restaurant_id,
        area_id=area_id,
        floor_plan_id=floor_plan_id,
        rule_id=rule_id,
        owner_id=current_user.id,
        new_status=payload.status,
    )

    await service.rule_repository.db.commit()

    if rule is None:
        return None

    return serialize_rule(rule)