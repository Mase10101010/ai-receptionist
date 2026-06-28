import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.services.integration_service import IntegrationService


router = APIRouter(prefix="/integrations", tags=["integrations"])


class SevenRoomsConnectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: uuid.UUID
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    venue_id: str = Field(..., min_length=1)
    venue_group_id: str = Field(..., min_length=1)
    base_url: str = "https://api.sevenrooms.com"


@router.post("/sevenrooms/connect")
async def connect_sevenrooms(
    payload: SevenRoomsConnectPayload,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)

    return await service.connect_sevenrooms(
        restaurant_id=payload.restaurant_id,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        venue_id=payload.venue_id,
        venue_group_id=payload.venue_group_id,
        base_url=payload.base_url,
    )