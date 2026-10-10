"""Security tests for customer reservation access in public chat."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.chat import send_public_message
from app.schemas.chat import ChatRequest
from app.services.reservation_access_context import ReservationAccessContext


@pytest.fixture
def chat_setup():
    restaurant_id = uuid.uuid4()
    restaurant = SimpleNamespace(
        id=restaurant_id,
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
async def test_public_chat_without_token_has_no_access_context(chat_setup):
    restaurant, ai_service, db = chat_setup

    with patch(
        "app.api.v1.endpoints.chat.RestaurantRepository"
    ) as repo_class:
        repo_class.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )

        response = await send_public_message(
            restaurant_slug="test-restaurant",
            payload=ChatRequest(message="Vorrei prenotare"),
            ai_service=ai_service,
            db=db,
        )

    assert response.session_id == "session-123"
    assert ai_service.handle_message.await_args.kwargs["access_context"] is None


@pytest.mark.asyncio
async def test_valid_token_passes_verified_context(chat_setup):
    restaurant, ai_service, db = chat_setup

    context = ReservationAccessContext(
        restaurant_id=restaurant.id,
        reservation_id=uuid.uuid4(),
    )

    with (
        patch("app.api.v1.endpoints.chat.RestaurantRepository") as repo_class,
        patch(
            "app.api.v1.endpoints.chat.ReservationAccessService"
        ) as access_class,
    ):
        repo_class.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )
        access_class.return_value.resolve = AsyncMock(
            return_value=context
        )

        await send_public_message(
            restaurant_slug="test-restaurant",
            payload=ChatRequest(
                message="Vorrei modificare la prenotazione",
                reservation_access_token="valid-customer-token",
            ),
            ai_service=ai_service,
            db=db,
        )

    access_class.return_value.resolve.assert_awaited_once_with(
        "valid-customer-token",
        restaurant.id,
    )

    assert (
        ai_service.handle_message.await_args.kwargs["access_context"]
        is context
    )

    assert "valid-customer-token" not in str(
        ai_service.handle_message.await_args
    )


@pytest.mark.asyncio
async def test_invalid_token_rejected_before_ai_call(chat_setup):
    restaurant, ai_service, db = chat_setup

    with (
        patch("app.api.v1.endpoints.chat.RestaurantRepository") as repo_class,
        patch(
            "app.api.v1.endpoints.chat.ReservationAccessService"
        ) as access_class,
    ):
        repo_class.return_value.get_by_slug = AsyncMock(
            return_value=restaurant
        )
        access_class.return_value.resolve = AsyncMock(
            return_value=None
        )

        with pytest.raises(HTTPException) as exc:
            await send_public_message(
                restaurant_slug="test-restaurant",
                payload=ChatRequest(
                    message="Cancella la prenotazione",
                    reservation_access_token="invalid-token",
                ),
                ai_service=ai_service,
                db=db,
            )

    assert exc.value.status_code == 403
    ai_service.handle_message.assert_not_awaited()
