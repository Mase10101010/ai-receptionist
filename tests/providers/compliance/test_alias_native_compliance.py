import uuid

import pytest

import app.providers.native.provider
from app.db.session import AsyncSessionLocal
from app.providers.contract.refs import ProviderType
from app.providers.resolver import ProviderResolver
from tests.providers.compliance.base import (
    run_basic_provider_lifecycle_compliance,
)


RESTAURANT_ID = uuid.UUID("77488b28-620b-49f2-9148-d3539c9cf6d0")


@pytest.mark.asyncio
async def test_alias_native_provider_compliance_basic_lifecycle():
    session = AsyncSessionLocal()

    try:
        provider = await ProviderResolver().resolve(session, RESTAURANT_ID)

        await run_basic_provider_lifecycle_compliance(
            session=session,
            provider=provider,
            restaurant_id=RESTAURANT_ID,
            expected_provider_type=ProviderType.ALIAS_NATIVE,
        )

    finally:
        await session.close()