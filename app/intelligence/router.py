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

    reservation_repository = (
        ReservationRepository(
            session,
        )
    )

    if payload.suggestion_id is not None:
        await (
            IntelligenceExecutionGate(
                repository=(
                    AISuggestionRepository(
                        session,
                    )
                ),
            )
            .validate_reoptimization(
                suggestion_id=(
                    payload.suggestion_id
                ),
                allowed_restaurant_ids=(
                    allowed_restaurant_ids
                ),
                new_reservation_id=(
                    payload.new_reservation_id
                ),
                new_reservation_table_ids=(
                    payload
                    .new_reservation_table_ids
                ),
                new_reservation_primary_table_id=(
                    payload
                    .new_reservation_primary_table_id
                ),
                moves=[
                    move.model_dump()
                    for move in payload.moves
                ],
            )
        )

    result = (
        await service.apply_reoptimization(
            session=session,
            payload=payload,
            allowed_restaurant_ids=(
                allowed_restaurant_ids
            ),
        )
    )

    if payload.suggestion_id is not None:
        accepted_suggestion = await (
            AISuggestionService(
                repository=(
                    AISuggestionRepository(
                        session,
                    )
                ),
                reservation_repository=(
                    reservation_repository
                ),
                intelligence_service=service,
            )
            .accept(
                suggestion_id=(
                    payload.suggestion_id
                ),
                restaurant_ids=(
                    allowed_restaurant_ids
                ),
            )
        )

        if accepted_suggestion is None:
            raise ValidationError(
                "AI suggestion could not "
                "be accepted."
            )

    audit_reservation = await (
        reservation_repository
        .get_by_id_for_restaurants(
            reservation_id=(
                payload.new_reservation_id
            ),
            restaurant_ids=(
                allowed_restaurant_ids
            ),
        )
    )

    if (
        audit_reservation is None
        or audit_reservation.restaurant_id
        is None
    ):
        raise ValidationError(
            "Applied reservation could not "
            "be resolved for audit."
        )

    await (
        IntelligenceEventService(
            repository=(
                IntelligenceEventRepository(
                    session,
                )
            ),
        )
        .record(
            restaurant_id=(
                audit_reservation.restaurant_id
            ),
            event_type=(
                IntelligenceEventType
                .SEATING_PLAN_APPLIED
            ),
            source=(
                IntelligenceEventSource.MANAGER
            ),
            entity_type="reservation",
            entity_id=(
                payload.new_reservation_id
            ),
            actor_user_id=current_user.id,
            payload={
                "suggestion_id": (
                    str(payload.suggestion_id)
                    if payload.suggestion_id
                    is not None
                    else None
                ),
                "new_reservation_primary_table_id": (
                    str(
                        result
                        .new_reservation_primary_table_id
                    )
                ),
                "new_reservation_table_ids": [
                    str(table_id)
                    for table_id
                    in result
                    .new_reservation_table_ids
                ],
                "new_reservation_table_numbers": (
                    result
                    .new_reservation_table_numbers
                ),
                "moves": [
                    {
                        "reservation_id": str(
                            move.reservation_id
                        ),
                        "primary_table_id": str(
                            move.primary_table_id
                        ),
                        "table_ids": [
                            str(table_id)
                            for table_id
                            in move.table_ids
                        ],
                        "table_numbers": (
                            move.table_numbers
                        ),
                    }
                    for move
                    in result.applied_moves
                ],
                "mode": result.mode,
                "applied": result.applied,
            },
        )
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