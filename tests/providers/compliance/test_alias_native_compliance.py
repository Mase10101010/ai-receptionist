import uuid

import pytest

import app.providers.native.provider
from app.models.restaurant import Restaurant
from app.models.user import User
from app.providers.contract.refs import ProviderType
from app.providers.resolver import (
    NullIntegrationConfigStore,
    ProviderResolver,
)
from tests.providers.compliance.base import (
    run_basic_provider_lifecycle_compliance,
)


@pytest.mark.asyncio
async def test_alias_native_provider_compliance_basic_lifecycle(db_session):
    user = User(
        email=f"provider-compliance-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="Provider Compliance Restaurant",
        slug=f"provider-compliance-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
    )
    db_session.add(restaurant)
    await db_session.flush()

    provider = await ProviderResolver(
        config_store=NullIntegrationConfigStore(),
    ).resolve(
        db_session,
        restaurant.id,
    )

    await run_basic_provider_lifecycle_compliance(
        session=db_session,
        provider=provider,
        restaurant_id=restaurant.id,
        expected_provider_type=ProviderType.ALIAS_NATIVE,
    )
