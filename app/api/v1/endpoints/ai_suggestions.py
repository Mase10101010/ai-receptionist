from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)
from app.repositories.reservation_repository import (
    ReservationRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.schemas.ai_suggestion import (
    AISuggestionActionResponse,
    AISuggestionAnalyzeResponse,
    AISuggestionListResponse,
    AISuggestionResponse,
)
from app.services.ai_suggestion_service import (
    AISuggestionService,
)


router = APIRouter(
    prefix="/ai-suggestions",
    tags=["ai-suggestions"],
)


async def get_allowed_restaurant_ids(
    current_user: CurrentUserDep,
    session: AsyncSession,
) -> list[uuid.UUID]:
    repository = RestaurantRepository(session)

    restaurants = await repository.list_by_owner(
        current_user.id,
    )

    return [
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    ]


def build_service(
    session: AsyncSession,
) -> AISuggestionService:
    return AISuggestionService(
        repository=AISuggestionRepository(session),
        reservation_repository=ReservationRepository(
            session,
        ),
    )


@router.get(
    "",
    response_model=AISuggestionListResponse,
)
async def list_ai_suggestions(
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
) -> AISuggestionListResponse:
    restaurant_ids = await get_allowed_restaurant_ids(
        current_user=current_user,
        session=session,
    )

    service = build_service(session)

    suggestions = await service.list_pending(
        restaurant_ids=restaurant_ids,
        limit=limit,
    )

    return AISuggestionListResponse(
        suggestions=[
            AISuggestionResponse.model_validate(
                suggestion,
            )
            for suggestion in suggestions
        ],
        total=len(suggestions),
    )


@router.post(
    "/analyze/{reservation_id}",
    response_model=AISuggestionAnalyzeResponse,
)
async def analyze_ai_suggestion(
    reservation_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> AISuggestionAnalyzeResponse:
    restaurant_ids = await get_allowed_restaurant_ids(
        current_user=current_user,
        session=session,
    )

    service = build_service(session)

    suggestion = (
        await service.analyze_reservation_by_id(
            reservation_id=reservation_id,
            restaurant_ids=restaurant_ids,
        )
    )

    if suggestion is None:
        return AISuggestionAnalyzeResponse(
            created=False,
            suggestion=None,
        )

    await session.commit()

    return AISuggestionAnalyzeResponse(
        created=True,
        suggestion=(
            AISuggestionResponse.model_validate(
                suggestion,
            )
        ),
    )


@router.post(
    "/{suggestion_id}/read",
    response_model=AISuggestionActionResponse,
)
async def mark_ai_suggestion_read(
    suggestion_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> AISuggestionActionResponse:
    restaurant_ids = await get_allowed_restaurant_ids(
        current_user=current_user,
        session=session,
    )

    service = build_service(session)

    suggestion = await service.mark_read(
        suggestion_id=suggestion_id,
        restaurant_ids=restaurant_ids,
    )

    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI suggestion not found",
        )

    await session.commit()

    return AISuggestionActionResponse(
        id=suggestion.id,
        status=suggestion.status,
        is_read=suggestion.is_read,
        updated_at=suggestion.updated_at,
    )


@router.post(
    "/{suggestion_id}/dismiss",
    response_model=AISuggestionActionResponse,
)
async def dismiss_ai_suggestion(
    suggestion_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> AISuggestionActionResponse:
    restaurant_ids = await get_allowed_restaurant_ids(
        current_user=current_user,
        session=session,
    )

    service = build_service(session)

    suggestion = await service.dismiss(
        suggestion_id=suggestion_id,
        restaurant_ids=restaurant_ids,
    )

    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI suggestion not found",
        )

    await session.commit()

    return AISuggestionActionResponse(
        id=suggestion.id,
        status=suggestion.status,
        is_read=suggestion.is_read,
        updated_at=suggestion.updated_at,
    )


@router.post(
    "/{suggestion_id}/accept",
    response_model=AISuggestionActionResponse,
)
async def accept_ai_suggestion(
    suggestion_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> AISuggestionActionResponse:
    restaurant_ids = await get_allowed_restaurant_ids(
        current_user=current_user,
        session=session,
    )

    service = build_service(session)

    suggestion = await service.accept(
        suggestion_id=suggestion_id,
        restaurant_ids=restaurant_ids,
    )

    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI suggestion not found",
        )

    await session.commit()

    return AISuggestionActionResponse(
        id=suggestion.id,
        status=suggestion.status,
        is_read=suggestion.is_read,
        updated_at=suggestion.updated_at,
    )