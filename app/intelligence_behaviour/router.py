from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
)
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
)
from app.intelligence_behaviour.service import (
    IntelligenceBehaviourService,
)
from app.intelligence_features.repository import (
    IntelligenceFeatureRepository,
)
from app.intelligence_features.service import (
    IntelligenceFeatureService,
)
from app.models.user import User
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)


router = APIRouter(
    prefix="/intelligence/behaviour",
    tags=["Intelligence Behaviour"],
)


@router.get(
    "/ai-suggestions",
    response_model=AISuggestionBehaviourProfile,
)
async def get_ai_suggestion_behaviour(
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
) -> AISuggestionBehaviourProfile:
    restaurant_repository = (
        RestaurantRepository(db)
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

    feature_service = IntelligenceFeatureService(
        IntelligenceFeatureRepository(db)
    )

    features = await feature_service.get_ai_suggestion_features(
        restaurant_id=restaurant_id,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
    )

    behaviour_service = IntelligenceBehaviourService()

    return behaviour_service.build_ai_suggestion_profile(
        features=features,
    )