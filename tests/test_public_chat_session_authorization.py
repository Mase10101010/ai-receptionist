"""Security tests for public conversation capability authorization."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.conversation_repository import ConversationRepository
from app.services.public_chat_session_service import PublicChatSessionService


@pytest.fixture
def session_setup():
    restaurant_id = uuid.uuid4()
    conversation = SimpleNamespace(
        id=uuid.uuid4(),
        session_id=uuid.uuid4().hex,
        restaurant_id=restaurant_id,
        public_access_token_hash=None,
    )
    token = PublicChatSessionService.issue(conversation)

    repo = ConversationRepository(AsyncMock())
    repo.get_by_session_id = AsyncMock(return_value=conversation)

    return repo, conversation, restaurant_id, token


@pytest.mark.asyncio
async def test_missing_token_denied(session_setup):
    repo, conversation, restaurant_id, _ = session_setup

    result = await repo.get_authorized_public_session(
        conversation.session_id, restaurant_id, None
    )

    assert result is None
    repo.get_by_session_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_incorrect_token_denied(session_setup):
    repo, conversation, restaurant_id, _ = session_setup

    result = await repo.get_authorized_public_session(
        conversation.session_id,
        restaurant_id,
        "incorrect-token-value",
    )

    assert result is None


@pytest.mark.asyncio
async def test_unknown_session_denied(session_setup):
    repo, _, restaurant_id, token = session_setup
    repo.get_by_session_id.return_value = None

    result = await repo.get_authorized_public_session(
        uuid.uuid4().hex, restaurant_id, token
    )

    assert result is None


@pytest.mark.asyncio
async def test_other_conversation_token_denied(session_setup):
    repo, conversation, restaurant_id, _ = session_setup

    other_conversation = SimpleNamespace(public_access_token_hash=None)
    other_token = PublicChatSessionService.issue(other_conversation)

    result = await repo.get_authorized_public_session(
        conversation.session_id, restaurant_id, other_token
    )

    assert result is None


@pytest.mark.asyncio
async def test_valid_token_authorized(session_setup):
    repo, conversation, restaurant_id, token = session_setup

    result = await repo.get_authorized_public_session(
        conversation.session_id, restaurant_id, token
    )

    assert result is conversation
    repo.get_by_session_id.assert_awaited_once_with(
        conversation.session_id, restaurant_id
    )
