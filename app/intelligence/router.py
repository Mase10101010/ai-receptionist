from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.core.exceptions import ValidationError
from app.db.session import get_db

from app.intelligence_execution.gate import (
    IntelligenceExecutionGate,
)

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_events.service import (
    IntelligenceEventService,
)

from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)
from app.repositories.reservation_repository import (
    ReservationRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)

from app.services.ai_suggestion_service import (
    AISuggestionService,
)

from app.intelligence_events.schemas import (
    IntelligenceEventResponse,
)

from app.intelligence_execution.orchestrator import (
    IntelligenceExecutionOrchestrator,
)

from .schemas import (
    IntelligenceApplyRequest,
    IntelligenceApplyResponse,
    IntelligenceOptimizeRequest,
    IntelligenceOptimizeResponse,
    IntelligenceReoptimizeRequest,
    IntelligenceReoptimizeResponse,
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
)
from .sqlalchemy_service import (
    IntelligenceOptimizationService,
)


router = APIRouter(
    prefix="/intelligence",
    tags=["intelligence"],
)

service = IntelligenceOptimizationService()


@router.post(
    "/optimize",
    response_model=IntelligenceOptimizeResponse,
)
async def optimize_reservation(
    payload: IntelligenceOptimizeRequest,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceOptimizeResponse:
    return await service.optimize(
        session=session,
        payload=payload,
    )


@router.post(
    "/reoptimize",
    response_model=IntelligenceReoptimizeResponse,
)
async def reoptimize_reservation(
    payload: IntelligenceReoptimizeRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceReoptimizeResponse:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = {
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    }

    if (
        payload.restaurant_id
        not in allowed_restaurant_ids
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Restaurant not found",
        )

    return await service.reoptimize(
        session=session,
        payload=payload,
    )


@router.post(
    "/apply-reoptimization",
    response_model=(
        IntelligenceApplyReoptimizationResponse
    ),
)
async def apply_reoptimization(
    payload: IntelligenceApplyReoptimizationRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceApplyReoptimizationResponse:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = [
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    ]

    result = await IntelligenceExecutionOrchestrator(
        intelligence_service=service,
    ).apply_reoptimization(
        session=session,
        payload=payload,
        allowed_restaurant_ids=allowed_restaurant_ids,
        source=IntelligenceEventSource.MANAGER,
        actor_user_id=current_user.id,
    )

    await session.commit()

    return result


@router.post(
    "/apply",
    response_model=IntelligenceApplyResponse,
)
async def apply_recommendation(
    payload: IntelligenceApplyRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceApplyResponse:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = [
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    ]

    result = (
        await service.apply_recommendation(
            session=session,
            payload=payload,
            allowed_restaurant_ids=(
                allowed_restaurant_ids
            ),
        )
    )

    await session.commit()

    return result

@router.get(
    "/events",
    response_model=list[IntelligenceEventResponse],
)
async def list_intelligence_events(
    restaurant_id: UUID,
    current_user: CurrentUserDep,
    event_type: IntelligenceEventType | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> list[IntelligenceEventResponse]:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = {
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    }

    if (
        restaurant_id
        not in allowed_restaurant_ids
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Restaurant not found",
        )

    events = await (
        IntelligenceEventService(
            repository=(
                IntelligenceEventRepository(
                    session,
                )
            ),
        )
        .list_restaurant_events(
            restaurant_id=restaurant_id,
            limit=min(
                max(limit, 1),
                500,
            ),
            offset=max(
                offset,
                0,
            ),
            event_type=event_type,
        )
    )

    return [
        IntelligenceEventResponse
        .model_validate(event)
        for event in events
    ]