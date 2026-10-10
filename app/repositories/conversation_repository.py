"""
Conversation repository.

Handles persistence of chat sessions and their messages. The history-loading
methods support our "conversation memory" feature — without them, every chat
turn would be context-free and the AI couldn't remember anything earlier in
the conversation.
"""
import uuid
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole
from app.services.public_chat_session_service import PublicChatSessionService


class ConversationRepository:
    """Async data access for chat sessions and messages."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Conversations ─────────────────────────────────────────────────────
    async def get_by_session_id(
        self,
        session_id: str,
        restaurant_id: uuid.UUID,
    ) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.session_id == session_id,
                Conversation.restaurant_id == restaurant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_authorized_public_session(
        self,
        session_id: str,
        restaurant_id: uuid.UUID,
        token: str | None,
    ) -> Conversation | None:
        """Return a public conversation only with a valid capability."""
        if token is None:
            return None

        conversation = await self.get_by_session_id(
            session_id,
            restaurant_id,
        )

        if conversation is None:
            return None

        if not PublicChatSessionService.verify(conversation, token):
            return None

        return conversation

    async def create(
        self,
        session_id: str,
        restaurant_id: uuid.UUID,
    ) -> Conversation:
        conversation = Conversation(
            session_id=session_id,
            restaurant_id=restaurant_id,
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def create_public_session(
        self,
        restaurant_id: uuid.UUID,
    ) -> tuple[Conversation, str]:
        """Create a public session with a server-issued private capability."""
        session_id = uuid.uuid4().hex
        conversation = await self.create(session_id, restaurant_id)

        token = PublicChatSessionService.issue(conversation)
        await self.db.flush()

        return conversation, token

    async def get_or_create(
        self,
        session_id: str,
        restaurant_id: uuid.UUID,
    ) -> tuple[Conversation, bool]:
        existing = await self.get_by_session_id(
            session_id,
            restaurant_id,
        )
        if existing:
            return existing, False

        # A session ID must never be reused across restaurants.
        result = await self.db.execute(
            select(Conversation.id).where(
                Conversation.session_id == session_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValueError("Conversation session belongs to another restaurant")

        return await self.create(session_id, restaurant_id), True

    async def touch(self, conversation: Conversation) -> None:
        conversation.last_active_at = datetime.utcnow()
        await self.db.flush()

    async def update_customer_info(
        self,
        conversation: Conversation,
        name: str | None = None,
        phone: str | None = None,
    ) -> None:
        if name is not None:
            conversation.customer_name = name
        if phone is not None:
            conversation.customer_phone = phone
        await self.db.flush()

    # ── MESSAGES ──────────────────────────────────────────────────────────
    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
    ) -> Message:
        """
        FIX CRITICO:
        Forziamo conversione corretta verso ENUM PostgreSQL.
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,  # 👈 FIX: garantisce compatibilità ENUM
            content=content,
        )

        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_recent_messages(
        self, conversation_id: uuid.UUID, limit: int
    ) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def get_full_history(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())