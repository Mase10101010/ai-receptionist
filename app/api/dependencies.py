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
from app.repositories.table_repository import TableRepository       
from app.repositories.user_repository import UserRepository
from app.services.ai_service import AIService
from app.services.email_service import EmailService
from app.services.reservation_service import ReservationService


security = HTTPBearer()

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_reservation_service(db: DbSession) -> ReservationService:
    reservation_repo = ReservationRepository(db)
    restaurant_repo = RestaurantRepository(db)
    table_repo = TableRepository(db)
    email_service = EmailService()

    return ReservationService(
        reservation_repo, 
        restaurant_repo,
        table_repo,
        email_service,
    )


def get_ai_service(db: DbSession) -> AIService:
    conversation_repo = ConversationRepository(db)
    reservation_repo = ReservationRepository(db)
    restaurant_repo = RestaurantRepository(db)
    table_repo = TableRepository(db)
    email_service = EmailService()
    reservation_service = ReservationService(
        reservation_repo,
        restaurant_repo,
        table_repo,
        email_service,
    )
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

async def get_active_restaurant_for_current_user(
    current_user: CurrentUserDep,
    db: DbSession,
):
    restaurant_repo = RestaurantRepository(db)

    restaurants = await restaurant_repo.list_by_owner(
        current_user.id
    )

    if not restaurants:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No restaurant found for this account",
        )

    restaurant = restaurants[0]

    if restaurant.subscription_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    return restaurant


ActiveRestaurantDep = Annotated[
    object,
    Depends(get_active_restaurant_for_current_user),
]

async def get_active_restaurant_by_id_for_current_user(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbSession,
):
    restaurant_repo = RestaurantRepository(db)

    restaurant = await restaurant_repo.get_by_id_for_owner(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
    )

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found",
        )

    if restaurant.subscription_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    return restaurant


ActiveRestaurantByIdDep = Annotated[
    object,
    Depends(get_active_restaurant_by_id_for_current_user),
]