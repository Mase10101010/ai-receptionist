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
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)
from app.intelligence_policy.schemas import (
    RecommendationPolicy,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)


router = APIRouter(
    prefix="/intelligence/policy",
    tags=["Intelligence Policy"],
)


@router.get(
    "/ai-suggestions",
    response_model=RecommendationPolicy,
)
async def get_ai_suggestion_policy(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
) -> RecommendationPolicy:
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

    service = IntelligenceOptimizationService()

    policy = await service._build_recommendation_policy(
        session=db,
        restaurant_id=restaurant_id,
    )

    if policy is None:
        raise NotFoundError(
            "Recommendation policy not available yet"
        )

    return policy