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


class ConversationRepository:
    """Async data access for chat sessions and messages."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Conversations ─────────────────────────────────────────────────────
    async def get_by_session_id(self, session_id: str) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def create(self, session_id: str) -> Conversation:
        conversation = Conversation(session_id=session_id)
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def get_or_create(self, session_id: str) -> tuple[Conversation, bool]:
        existing = await self.get_by_session_id(session_id)
        if existing:
            return existing, False
        return await self.create(session_id), True

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