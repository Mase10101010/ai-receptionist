from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import RestaurantIntegration
from app.providers.context import (
    IntegrationConfig,
    IntegrationMode,
    IntegrationStatus,
)
from app.providers.contract.availability import AliasVenueId
from app.providers.contract.refs import ProviderType


class SqlAlchemyIntegrationConfigStore:
    async def get_for_venue(
        self,
        session: AsyncSession,
        venue_id: AliasVenueId,
    ) -> IntegrationConfig | None:
        result = await session.execute(
            select(RestaurantIntegration).where(
                RestaurantIntegration.restaurant_id == venue_id
            )
        )

        integration = result.scalar_one_or_none()

        if integration is None:
            return None

        return IntegrationConfig(
            venue_id=AliasVenueId(integration.restaurant_id),
            provider_type=ProviderType(integration.provider_type.value),
            mode=IntegrationMode(integration.mode.value),
            status=IntegrationStatus(integration.status.value),
            timezone=integration.timezone,
            locale=integration.locale,
            currency=integration.currency,
            settings=integration.settings or {},
            encrypted_credentials=integration.encrypted_credentials,
        )