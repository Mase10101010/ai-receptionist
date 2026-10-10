"""Private capabilities for continuing public chat sessions."""

import hashlib
import hmac
import secrets

from app.models.conversation import Conversation


class PublicChatSessionService:
    """Issue and verify private capabilities for public conversations."""

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, conversation: Conversation) -> str:
        """Assign a new private capability to a conversation."""
        token = secrets.token_urlsafe(32)
        conversation.public_access_token_hash = cls._hash_token(token)
        return token

    @classmethod
    def verify(cls, conversation: Conversation, token: str | None) -> bool:
        """Reject missing, malformed or incorrect capabilities."""
        stored_hash = conversation.public_access_token_hash

        if (
            stored_hash is None
            or not isinstance(token, str)
            or not 32 <= len(token) <= 512
        ):
            return False

        candidate_hash = cls._hash_token(token)
        return hmac.compare_digest(stored_hash, candidate_hash)
