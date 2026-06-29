import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

import app.providers.sevenrooms.provider
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


class IntegrationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def connect_sevenrooms(
        self,
        *,
        restaurant_id: uuid.UUID,
        client_id: str,
        client_secret: str,
        venue_id: str,
        venue_group_id: str,
        base_url: str,
    ):
        crypto = CredentialEncryptionService.from_settings()

        encrypted_credentials = await crypto.encrypt(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "venue_id": venue_id,
                "venue_group_id": venue_group_id,
            }
        )

        await self.db.execute(
            delete(RestaurantIntegration).where(
                RestaurantIntegration.restaurant_id == restaurant_id
            )
        )

        integration = RestaurantIntegration(
            restaurant_id=restaurant_id,
            provider_type=DbProviderType.SEVENROOMS,
            mode=IntegrationMode.CONNECT,
            status=IntegrationStatus.ACTIVE,
            timezone="Australia/Perth",
            settings={
                "venue_id": venue_id,
                "venue_group_id": venue_group_id,
                "base_url": base_url,
            },
            encrypted_credentials=encrypted_credentials,
        )

        self.db.add(integration)
        await self.db.commit()

        resolver = ProviderResolver(
            config_store=SqlAlchemyIntegrationConfigStore(),
            credential_decryptor=FernetCredentialDecryptor(),
        )

        provider = await resolver.resolve(self.db, restaurant_id)
        return await provider.diagnostics()