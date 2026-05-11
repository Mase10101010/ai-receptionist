"""
Dependency injection wiring for the API layer.

FastAPI's `Depends` system lets us declare what each endpoint needs (a DB
session, a service, etc.) and resolves them automatically. Centralizing the
factories here means endpoint files stay focused on routing and validation.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.reservation_repository import ReservationRepository
from app.services.ai_service import AIService
from app.services.reservation_service import ReservationService

# Type alias — saves us repeating Annotated[..., Depends(...)] in every endpoint.
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_reservation_service(db: DbSession) -> ReservationService:
    """Build a ReservationService bound to the request's DB session."""
    repo = ReservationRepository(db)
    return ReservationService(repo)


def get_ai_service(db: DbSession) -> AIService:
    """
    Build an AIService.

    AIService depends on both repositories and on ReservationService, so we
    construct the whole graph here.
    """
    conversation_repo = ConversationRepository(db)
    reservation_repo = ReservationRepository(db)
    reservation_service = ReservationService(reservation_repo)
    return AIService(conversation_repo, reservation_service)


def get_conversation_repository(db: DbSession) -> ConversationRepository:
    """Direct repo access for read-only history endpoints."""
    return ConversationRepository(db)


# Convenience type aliases for endpoint signatures
ReservationServiceDep = Annotated[ReservationService, Depends(get_reservation_service)]
AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
ConversationRepoDep = Annotated[
    ConversationRepository, Depends(get_conversation_repository)
]
