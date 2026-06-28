import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

import app.providers.sevenrooms.provider
from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.models.integration import (
    IntegrationMode,
    IntegrationStatus,
    ProviderType as DbProviderType,
    RestaurantIntegration,
)
from app.providers.credential_crypto import CredentialEncryptionService
from app.providers.credential_decryptor import FernetCredentialDecryptor
from app.providers.integration_store import SqlAlchemyIntegrationConfigStore
from app.providers.resolver import ProviderResolver


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
    # TODO: verify restaurant ownership before production use.
    key = CredentialEncryptionService.generate_key()
    crypto = CredentialEncryptionService(key)

    encrypted_credentials = await crypto.encrypt(
        {
            "client_id": payload.client_id,
            "client_secret": payload.client_secret,
            "venue_id": payload.venue_id,
            "venue_group_id": payload.venue_group_id,
        }
    )

    await db.execute(
        delete(RestaurantIntegration).where(
            RestaurantIntegration.restaurant_id == payload.restaurant_id
        )
    )

    integration = RestaurantIntegration(
        restaurant_id=payload.restaurant_id,
        provider_type=DbProviderType.SEVENROOMS,
        mode=IntegrationMode.CONNECT,
        status=IntegrationStatus.ACTIVE,
        timezone="Australia/Perth",
        settings={
            "venue_id": payload.venue_id,
            "venue_group_id": payload.venue_group_id,
            "base_url": payload.base_url,
        },
        encrypted_credentials=encrypted_credentials,
    )

    db.add(integration)
    await db.commit()

    resolver = ProviderResolver(
        config_store=SqlAlchemyIntegrationConfigStore(),
        credential_decryptor=FernetCredentialDecryptor(key),
    )

    provider = await resolver.resolve(db, payload.restaurant_id)
    return await provider.diagnostics()