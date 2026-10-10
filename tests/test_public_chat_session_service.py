"""Security tests for public chat session capabilities."""

import hashlib

from app.models.conversation import Conversation
from app.services.public_chat_session_service import PublicChatSessionService


def make_conversation() -> Conversation:
    return Conversation(session_id="test-session")


def test_issued_token_verifies_for_own_conversation():
    conversation = make_conversation()

    token = PublicChatSessionService.issue(conversation)

    assert PublicChatSessionService.verify(conversation, token)
    assert conversation.public_access_token_hash == hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
    assert conversation.public_access_token_hash != token


def test_missing_and_incorrect_tokens_are_rejected():
    conversation = make_conversation()
    PublicChatSessionService.issue(conversation)

    assert not PublicChatSessionService.verify(conversation, None)
    assert not PublicChatSessionService.verify(conversation, "")
    assert not PublicChatSessionService.verify(conversation, "wrong")
    assert not PublicChatSessionService.verify(conversation, "x" * 513)


def test_token_from_another_conversation_is_rejected():
    first = make_conversation()
    second = make_conversation()

    first_token = PublicChatSessionService.issue(first)
    PublicChatSessionService.issue(second)

    assert not PublicChatSessionService.verify(second, first_token)


def test_reissuing_token_invalidates_previous_token():
    conversation = make_conversation()

    old_token = PublicChatSessionService.issue(conversation)
    new_token = PublicChatSessionService.issue(conversation)

    assert old_token != new_token
    assert not PublicChatSessionService.verify(conversation, old_token)
    assert PublicChatSessionService.verify(conversation, new_token)


def test_conversation_without_capability_rejects_token():
    conversation = make_conversation()

    assert not PublicChatSessionService.verify(
        conversation,
        "a" * 43,
    )
