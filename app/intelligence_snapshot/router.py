from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db,
)
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.intelligence_snapshot.schemas import (
    IntelligenceSnapshotResponse,
)
from app.intelligence_snapshot.service import (
    IntelligenceSnapshotService,
)
from app.models.user import User
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)


router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence Snapshot"],
)


@router.get(
    "/snapshot",
    response_model=IntelligenceSnapshotResponse,
)
async def get_intelligence_snapshot(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        get_current_user,
    ),
) -> IntelligenceSnapshotResponse:
    restaurant_repository = (
        RestaurantRepository(db)
    )

    restaurant = (
        await restaurant_repository.get_by_id(
            restaurant_id,
        )
    )

    if restaurant is None:
        raise NotFoundError(
            f"Restaurant {restaurant_id} not found"
        )

    if restaurant.owner_id != current_user.id:
        raise ValidationError(
            "Restaurant is not available "
            "for the current user."
        )

    service = IntelligenceSnapshotService(
        session=db,
    )

    snapshot = await service.build_snapshot(
        restaurant_id=restaurant_id,
    )

    if snapshot is None:
        raise NotFoundError(
            "Intelligence snapshot not available yet"
        )

    return snapshot