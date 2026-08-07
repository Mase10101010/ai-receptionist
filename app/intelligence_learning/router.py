from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.db.session import get_db
from app.intelligence_learning.schemas import (
    RestaurantLearningProfileResponse,
)
from app.intelligence_learning.service import (
    RestaurantLearningService,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)


router = APIRouter(
    prefix="/intelligence/learning",
    tags=["Intelligence Learning"],
)


@router.get(
    "/profile",
    response_model=RestaurantLearningProfileResponse,
)
async def get_learning_profile(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
) -> RestaurantLearningProfileResponse:
    restaurant_repository = RestaurantRepository(
        db,
    )

    restaurant = await restaurant_repository.get_by_id(
        restaurant_id,
    )

    if restaurant is None:
        raise NotFoundError(
            f"Restaurant {restaurant_id} not found"
        )

    if restaurant.owner_id != current_user.id:
        raise ValidationError(
            "Restaurant is not available for the current user."
        )

    service = RestaurantLearningService(
        session=db,
    )

    profile = await service.get_profile(
        restaurant_id=restaurant_id,
    )

    if profile is None:
        raise NotFoundError(
            "Learning profile not found"
        )

    return RestaurantLearningProfileResponse.model_validate(
        profile
    )