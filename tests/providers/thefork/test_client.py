import pytest

from app.providers.thefork.client import TheForkClient, TheForkClientConfig


class FakeHttpClient:
    async def post(self, path: str, *, json: dict):
        return {
            "access_token": "real-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }


@pytest.mark.asyncio
async def test_authenticate_uses_oauth_token_url():
    client = TheForkClient(
        TheForkClientConfig(
            client_id="client-id",
            client_secret="client-secret",
            restaurant_id="restaurant-id",
            token_url="/oauth/token",
            scopes=("reservations:write",),
        )
    )

    client._http = FakeHttpClient()

    token = await client.authenticate()

    assert token == "real-token-123"

@pytest.mark.asyncio
async def test_authenticate_returns_mock_token_without_token_url():
    client = TheForkClient(
        TheForkClientConfig(
            client_id="client-id",
            client_secret="client-secret",
            restaurant_id="restaurant-id",
        )
    )

    token = await client.authenticate()

    assert token == "mock-thefork-token"