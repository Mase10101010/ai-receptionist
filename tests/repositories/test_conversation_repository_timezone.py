from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.conversation import Conversation
from app.repositories.conversation_repository import ConversationRepository


def test_conversation_last_active_default_is_utc_aware():
    column = Conversation.__table__.c.last_active_at

    assert column.type.timezone is True
    assert column.default is not None

    generated_at = column.default.arg(None)

    assert isinstance(generated_at, datetime)
    assert generated_at.tzinfo is not None
    assert generated_at.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_conversation_touch_uses_utc_aware_timestamp():
    db = MagicMock()
    db.flush = AsyncMock()

    conversation = SimpleNamespace(last_active_at=None)
    repository = ConversationRepository(db)

    await repository.touch(conversation)

    updated_at = conversation.last_active_at

    assert isinstance(updated_at, datetime)
    assert updated_at.tzinfo is not None
    assert updated_at.utcoffset() == timedelta(0)

    db.flush.assert_awaited_once()
