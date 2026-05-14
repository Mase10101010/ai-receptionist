"""Pydantic schemas for the chat endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import MessageRole


class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    restaurant_id: uuid.uuid | None = None
    # If session_id is omitted, the server creates a new conversation.
    session_id: str | None = Field(
        None,
        description="Existing session id, or omit to start a new conversation",
        max_length=64,
    )
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """The AI's reply plus session metadata."""
    session_id: str
    reply: str
    # If the AI created/cancelled a reservation during this turn,
    # we surface its id so the client can show a confirmation.
    reservation_id: uuid.UUID | None = None


class MessageResponse(BaseModel):
    """A single transcript message (for history endpoint)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    """Full transcript for a session."""
    session_id: str
    customer_name: str | None
    messages: list[MessageResponse]
