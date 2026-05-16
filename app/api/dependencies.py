"""
Dependency injection wiring for the API layer.
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_service import AIService
from app.services.reservation_service import ReservationService

security = HTTPBearer()

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_reservation_service(db: DbSession) -> ReservationService:
    reservation_repo = ReservationRepository(db)
    restaurant_repo = RestaurantRepository(db)
    return ReservationService(reservation_repo, restaurant_repo)


def get_ai_service(db: DbSession) -> AIService:
    conversation_repo = ConversationRepository(db)
    reservation_repo = ReservationRepository(db)
    restaurant_repo = RestaurantRepository(db)
    reservation_service = ReservationService(reservation_repo, restaurant_repo)
    return AIService(
        conversation_repo,
        reservation_service,
        restaurant_repo,
    )


def get_conversation_repository(db: DbSession) -> ConversationRepository:
    return ConversationRepository(db)


async def get_current_user(
    db: DbSession,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")

        if user_id is None:
            raise ValueError("Missing token subject")

        user_uuid = uuid.UUID(str(user_id))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(user_uuid)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


ReservationServiceDep = Annotated[ReservationService, Depends(get_reservation_service)]
AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
ConversationRepoDep = Annotated[
    ConversationRepository, Depends(get_conversation_repository)
]
CurrentUserDep = Annotated[User, Depends(get_current_user)]