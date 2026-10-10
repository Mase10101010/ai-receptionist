"""REST endpoints for the AI receptionist chat."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import AIServiceDep, ConversationRepoDep, CurrentUserDep
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.services.reservation_access_service import ReservationAccessService
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    MessageResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the AI receptionist",
)
async def send_message(
    payload: ChatRequest,
    ai_service: AIServiceDep,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    if payload.restaurant_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Restaurant ID is required",
        )

    restaurant_repo = RestaurantRepository(db)
    restaurant = await restaurant_repo.get_by_id_for_owner(
        restaurant_id=payload.restaurant_id,
        owner_id=current_user.id,
    )

    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found",
        )

    if restaurant.subscription_status not in {
        "active",
        "trialing",
        "lifetime",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    session_id, reply, reservation_id, reservation_status, modification_status = await ai_service.handle_message(
        payload.session_id,
        payload.message,
        restaurant.id,
    )

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        reservation_id=reservation_id,
        reservation_status=reservation_status,
        modification_status=modification_status,
    )


@router.post(
    "/public/{restaurant_slug}",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Public widget chat for a restaurant",
)
async def send_public_message(
    restaurant_slug: str,
    payload: ChatRequest,
    ai_service: AIServiceDep,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    restaurant_repo = RestaurantRepository(db)
    restaurant = await restaurant_repo.get_by_slug(restaurant_slug)

    if restaurant is None:
        raise NotFoundError(f"Restaurant '{restaurant_slug}' not found")
    
    if restaurant.subscription_status not in {
        "active",
        "trialing",
        "lifetime",
    }:
        raise NotFoundError(
            f"Restaurant '{restaurant_slug}' not found"
        )

    access_context = None

    if payload.reservation_access_token is not None:
        access_service = ReservationAccessService(db)
        access_context = await access_service.resolve(
            payload.reservation_access_token,
            restaurant.id,
        )

        if access_context is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired reservation access",
            )

    conversation_repo = ConversationRepository(db)
    public_session_token = None

    if payload.session_id is None:
        conversation, public_session_token = (
            await conversation_repo.create_public_session(restaurant.id)
        )
    else:
        conversation = await conversation_repo.get_authorized_public_session(
            payload.session_id,
            restaurant.id,
            payload.public_session_token,
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid public chat session",
            )

    session_id, reply, reservation_id, reservation_status, modification_status = await ai_service.handle_message(
        conversation.session_id,
        payload.message,
        restaurant.id,
        access_context=access_context,
    )

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        public_session_token=public_session_token,
        reservation_id=reservation_id,
        reservation_status=reservation_status,
        modification_status=modification_status,
    )


@router.get(
    "/{session_id}/history",
    response_model=ConversationHistoryResponse,
    summary="Get full chat history for a session",
)
async def get_history(
    session_id: str,
    repo: ConversationRepoDep,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
) -> ConversationHistoryResponse:
    restaurant_repo = RestaurantRepository(db)
    restaurants = await restaurant_repo.list_by_owner(current_user.id)

    conversation = None

    for restaurant in restaurants:
        candidate = await repo.get_by_session_id(
            session_id,
            restaurant.id,
        )
        if candidate is not None:
            conversation = candidate
            break

    if conversation is None:
        raise NotFoundError("Conversation not found")

    messages = await repo.get_full_history(conversation.id)

    return ConversationHistoryResponse(
        session_id=conversation.session_id,
        customer_name=conversation.customer_name,
        messages=[MessageResponse.model_validate(m) for m in messages],
    )
