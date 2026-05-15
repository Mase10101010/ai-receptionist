"""REST endpoints for the AI receptionist chat."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import AIServiceDep, ConversationRepoDep
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.repositories.restaurant_repository import RestaurantRepository
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
) -> ChatResponse:
    session_id, reply, reservation_id = await ai_service.handle_message(
        payload.session_id,
        payload.message,
        payload.restaurant_id,
    )

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        reservation_id=reservation_id,
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

    session_id, reply, reservation_id = await ai_service.handle_message(
        payload.session_id,
        payload.message,
        restaurant.id,
    )

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        reservation_id=reservation_id,
    )


@router.get(
    "/{session_id}/history",
    response_model=ConversationHistoryResponse,
    summary="Get full chat history for a session",
)
async def get_history(
    session_id: str,
    repo: ConversationRepoDep,
) -> ConversationHistoryResponse:
    conversation = await repo.get_by_session_id(session_id)

    if conversation is None:
        raise NotFoundError(f"No conversation with session_id={session_id}")

    messages = await repo.get_full_history(conversation.id)

    return ConversationHistoryResponse(
        session_id=conversation.session_id,
        customer_name=conversation.customer_name,
        messages=[MessageResponse.model_validate(m) for m in messages],
    )
