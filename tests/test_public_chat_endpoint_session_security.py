"""Endpoint-level public chat session authorization tests."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.chat import send_public_message
from app.schemas.chat import ChatRequest


@pytest.fixture
def endpoint_setup():
    restaurant = SimpleNamespace(
        id=uuid.uuid4(),
        subscription_status="active",
    )
    ai_service = SimpleNamespace(
        handle_message=AsyncMock(
            return_value=("session-123", "OK", None, None, None)
        )
    )
    db = AsyncMock()
    db.add = MagicMock()

    return restaurant, ai_service, db


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [None, "incorrect-token"],
)
async def test_existing_session_rejected_without_valid_token(
    endpoint_setup, token
):
    restaurant, ai_service, db = endpoint_setup

    with (
        patch("app.api.v1.endpoints.chat.RestaurantRepository") as restaurant_cls,
        patch("app.api.v1.endpoints.chat.ConversationRepository") as conversation_cls,
    ):
        restaurant_cls.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )
        conversation_cls.return_value.get_authorized_public_session = AsyncMock(
            return_value=None
        )

        with pytest.raises(HTTPException) as exc:
            await send_public_message(
                restaurant_slug="test-restaurant",
                payload=ChatRequest(
                    session_id="session-123",
                    public_session_token=token,
                    message="Show previous messages",
                ),
                ai_service=ai_service,
                db=db,
            )

        assert exc.value.status_code == 403
        ai_service.handle_message.assert_not_awaited()
        conversation_cls.return_value.create_public_session.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_session_rejected(endpoint_setup):
    restaurant, ai_service, db = endpoint_setup

    with (
        patch("app.api.v1.endpoints.chat.RestaurantRepository") as restaurant_cls,
        patch("app.api.v1.endpoints.chat.ConversationRepository") as conversation_cls,
    ):
        restaurant_cls.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )
        conversation_cls.return_value.get_authorized_public_session = AsyncMock(
            return_value=None
        )

        with pytest.raises(HTTPException) as exc:
            await send_public_message(
                restaurant_slug="test-restaurant",
                payload=ChatRequest(
                    session_id="unknown-session",
                    public_session_token="some-token",
                    message="Hello",
                ),
                ai_service=ai_service,
                db=db,
            )

        assert exc.value.status_code == 403
        ai_service.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_session_reaches_ai(endpoint_setup):
    restaurant, ai_service, db = endpoint_setup
    conversation = SimpleNamespace(session_id="session-123")

    with (
        patch("app.api.v1.endpoints.chat.RestaurantRepository") as restaurant_cls,
        patch("app.api.v1.endpoints.chat.ConversationRepository") as conversation_cls,
    ):
        restaurant_cls.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )
        conversation_cls.return_value.get_authorized_public_session = AsyncMock(
            return_value=conversation
        )

        response = await send_public_message(
            restaurant_slug="test-restaurant",
            payload=ChatRequest(
                session_id="session-123",
                public_session_token="valid-session-token",
                message="Hello again",
            ),
            ai_service=ai_service,
            db=db,
        )

        assert response.session_id == "session-123"
        assert response.public_session_token is None

        conversation_cls.return_value.get_authorized_public_session.assert_awaited_once_with(
            "session-123",
            restaurant.id,
            "valid-session-token",
        )
        ai_service.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_public_session_returns_private_capability(endpoint_setup):
    restaurant, ai_service, db = endpoint_setup
    conversation = SimpleNamespace(session_id="new-public-session")
    private_token = "server-issued-private-capability"

    ai_service.handle_message.return_value = (
        conversation.session_id,
        "Welcome!",
        None,
        None,
        None,
    )

    with (
        patch("app.api.v1.endpoints.chat.RestaurantRepository") as restaurant_cls,
        patch("app.api.v1.endpoints.chat.ConversationRepository") as conversation_cls,
    ):
        restaurant_cls.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )
        conversation_cls.return_value.create_public_session = AsyncMock(
            return_value=(conversation, private_token)
        )

        response = await send_public_message(
            restaurant_slug="test-restaurant",
            payload=ChatRequest(message="Hello"),
            ai_service=ai_service,
            db=db,
        )

        assert response.session_id == conversation.session_id
        assert response.public_session_token == private_token
        assert response.reply == "Welcome!"

        conversation_cls.return_value.create_public_session.assert_awaited_once_with(
            restaurant.id
        )
        conversation_cls.return_value.get_authorized_public_session.assert_not_called()

        ai_service.handle_message.assert_awaited_once()
        assert ai_service.handle_message.await_args.args[:3] == (
            conversation.session_id,
            "Hello",
            restaurant.id,
        )
