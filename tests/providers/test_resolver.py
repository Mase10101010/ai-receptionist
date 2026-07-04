from uuid import UUID

import pytest

from app.providers.context import (
    IntegrationConfig,
    IntegrationMode,
    IntegrationStatus,
)
from app.providers.contract.availability import AliasVenueId
from app.providers.contract.capabilities import ProviderCapabilities, SourceOfTruth
from app.providers.contract.refs import ProviderType
from app.providers.registry import ProviderRegistry
from app.providers.resolver import IntegrationUnavailable, ProviderResolver


class FakeProvider:
    provider_type = ProviderType.SEVENROOMS
    capabilities = ProviderCapabilities()
    source_of_truth = SourceOfTruth.EXTERNAL


class FakeConfigStore:
    def __init__(self, config):
        self.config = config

    async def get_for_venue(self, session, venue_id):
        return self.config


def fake_factory(context, deps):
    return FakeProvider()

class FakeNativeProvider:
    provider_type = ProviderType.ALIAS_NATIVE
    capabilities = ProviderCapabilities()
    source_of_truth = SourceOfTruth.ALIAS


def fake_native_factory(context, deps):
    return FakeNativeProvider()

@pytest.mark.asyncio
async def test_resolver_returns_configured_provider_when_integration_is_active():
    venue_id = AliasVenueId(UUID("11111111-1111-1111-1111-111111111111"))

    registry = ProviderRegistry()
    registry.register(ProviderType.SEVENROOMS, fake_factory)

    resolver = ProviderResolver(
        registry=registry,
        config_store=FakeConfigStore(
            IntegrationConfig(
                venue_id=venue_id,
                provider_type=ProviderType.SEVENROOMS,
                mode=IntegrationMode.CONNECT,
                status=IntegrationStatus.ACTIVE,
            )
        ),
    )

    provider = await resolver.resolve(
        session=None,
        venue_id=venue_id,
    )

    assert provider.provider_type == ProviderType.SEVENROOMS

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        IntegrationStatus.PENDING,
        IntegrationStatus.DISABLED,
        IntegrationStatus.ERROR,
    ],
)
async def test_resolver_raises_when_integration_is_not_active(status):
    venue_id = AliasVenueId(UUID("11111111-1111-1111-1111-111111111111"))

    registry = ProviderRegistry()
    registry.register(ProviderType.SEVENROOMS, fake_factory)

    resolver = ProviderResolver(
        registry=registry,
        config_store=FakeConfigStore(
            IntegrationConfig(
                venue_id=venue_id,
                provider_type=ProviderType.SEVENROOMS,
                mode=IntegrationMode.CONNECT,
                status=status,
            )
        ),
    )

    with pytest.raises(IntegrationUnavailable):
        await resolver.resolve(
            session=None,
            venue_id=venue_id,
        )

@pytest.mark.asyncio
async def test_resolver_returns_native_provider_when_no_integration_exists():
    venue_id = AliasVenueId(UUID("11111111-1111-1111-1111-111111111111"))

    registry = ProviderRegistry()
    registry.register(ProviderType.ALIAS_NATIVE, fake_native_factory)

    resolver = ProviderResolver(
        registry=registry,
        config_store=FakeConfigStore(None),
    )

    provider = await resolver.resolve(
        session=None,
        venue_id=venue_id,
    )

    assert provider.provider_type == ProviderType.ALIAS_NATIVE