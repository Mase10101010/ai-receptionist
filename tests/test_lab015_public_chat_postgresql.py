"""LAB-015: PostgreSQL persistence and isolation of public chat sessions."""

import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.restaurant import Restaurant
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.services.public_chat_session_service import PublicChatSessionService


@pytest.mark.asyncio
async def test_postgresql_public_session_persists_and_requires_capability():
    suffix = uuid.uuid4().hex
    user_id = None
    restaurant_id = None
    conversation_id = None

    try:
        async with AsyncSessionLocal() as session:
            user = User(
                email=f"lab015-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"LAB015 PostgreSQL {suffix}",
                slug=f"lab015-postgresql-{suffix}",
            )
            session.add(restaurant)
            await session.flush()
            restaurant_id = restaurant.id

            repo = ConversationRepository(session)
            conversation, token = await repo.create_public_session(
                restaurant_id
            )

            conversation_id = conversation.id
            session_id = conversation.session_id

            assert token
            assert conversation.public_access_token_hash != token
            assert conversation.public_access_token_hash == (
                PublicChatSessionService._hash_token(token)
            )

            await session.commit()

        # A fresh transaction must see the committed conversation.
        async with AsyncSessionLocal() as session:
            repo = ConversationRepository(session)

            stored = await session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id
                )
            )

            assert stored is not None
            assert stored.restaurant_id == restaurant_id
            assert stored.session_id == session_id
            assert stored.public_access_token_hash != token

            assert await repo.get_authorized_public_session(
                session_id, restaurant_id, token
            ) is not None

            assert await repo.get_authorized_public_session(
                session_id, restaurant_id, "incorrect-token"
            ) is None

            assert await repo.get_authorized_public_session(
                session_id, restaurant_id, None
            ) is None

            assert await repo.get_authorized_public_session(
                session_id, uuid.uuid4(), token
            ) is None

    finally:
        if user_id is not None:
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(
                    delete(User).where(User.id == user_id)
                )
                await cleanup.commit()
