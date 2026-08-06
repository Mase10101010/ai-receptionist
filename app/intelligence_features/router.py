from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
)
from app.intelligence_features.repository import (
    IntelligenceFeatureRepository,
)
from app.intelligence_features.schemas import (
    AISuggestionFeatures,
)
from app.intelligence_features.service import (
    IntelligenceFeatureService,
)
from app.models.user import User
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)

router = APIRouter(
    prefix="/intelligence/features",
    tags=["Intelligence Features"],
)


@router.get(
    "/ai-suggestions",
    response_model=AISuggestionFeatures,
)
async def get_ai_suggestion_features(
    restaurant_id: uuid.UUID,
    occurred_after: datetime | None = Query(
        default=None,
    ),
    occurred_before: datetime | None = Query(
        default=None,
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        get_current_user,
    ),
) -> AISuggestionFeatures:
    restaurant_repository = (
        RestaurantRepository(db)
    )

    restaurant = await restaurant_repository.get_by_id(
        restaurant_id,
    )

    if restaurant is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(
            f"Restaurant {restaurant_id} not found"
        )

    if restaurant.owner_id != current_user.id:
        from app.core.exceptions import ValidationError

        raise ValidationError(
            "Restaurant is not available for the current user."
        )

    service = IntelligenceFeatureService(
        IntelligenceFeatureRepository(db)
    )

    return await service.get_ai_suggestion_features(
        restaurant_id=restaurant_id,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
    )