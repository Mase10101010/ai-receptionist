from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

from .schemas import (
    IntelligenceApplyRequest,
    IntelligenceApplyResponse,
    IntelligenceOptimizeRequest,
    IntelligenceOptimizeResponse,
)
from .sqlalchemy_service import IntelligenceOptimizationService
from app.api.dependencies import CurrentUserDep
from app.repositories.restaurant_repository import RestaurantRepository

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
service = IntelligenceOptimizationService()


@router.post("/optimize", response_model=IntelligenceOptimizeResponse)
async def optimize_reservation(
    payload: IntelligenceOptimizeRequest,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceOptimizeResponse:
    return await service.optimize(session=session, payload=payload)

@router.post(
    "/apply",
    response_model=IntelligenceApplyResponse,
)
async def apply_recommendation(
    payload: IntelligenceApplyRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceApplyResponse:
    restaurant_repository = RestaurantRepository(session)

    restaurants = await restaurant_repository.list_by_owner(
        current_user.id,
    )

    allowed_restaurant_ids = [
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status in {
            "active",
            "trialing",
            "lifetime",
        }
    ]

    result = await service.apply_recommendation(
        session=session,
        payload=payload,
        allowed_restaurant_ids=allowed_restaurant_ids,
    )

    await session.commit()

    return result
