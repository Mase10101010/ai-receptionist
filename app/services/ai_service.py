"""
AI service — OpenAI integration with conversation memory and function calling.
"""

import json
import uuid
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.models.conversation import MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.reservation_service import ReservationService

logger = get_logger(__name__)


def _build_system_prompt(
    restaurant_name: str,
    timezone_name: str,
    opening_hour: int,
    closing_hour: int,
) -> str:
    return f"""\
You are the AI receptionist for {restaurant_name}, a fine-dining restaurant.

Your responsibilities:
  • Greet guests warmly and professionally.
  • Answer questions about hours, location, menu themes, and policies.
  • Help guests make, modify, or cancel reservations using the tools provided.
  • Be concise but friendly. Confirm details before creating a reservation.

Restaurant details:
  • Name: {restaurant_name}
  • Timezone: {timezone_name}
  • Hours: {opening_hour:02d}:00 - {closing_hour:02d}:00 daily
  • Maximum party size handled online: {settings.MAX_PARTY_SIZE}
  • For larger parties, ask the guest to call directly.

Reservation rules:
  • Always collect name, phone number, party size, and date/time before booking.
  • Interpret all guest-provided dates and times in the restaurant timezone.
  • Before confirming a slot, call check_availability.
  • If a requested time is unavailable, call suggest_alternative_slots and offer nearby available times.
  • After successfully booking, share the reservation id and recap.
  • Guests may update existing reservations by providing their reservation id.
  • If no year is provided, assume current or next occurrence.

Today is {datetime.utcnow().strftime("%A, %B %d, %Y")} (UTC).
"""


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check availability for a time slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_time": {
                        "type": "string",
                        "format": "date-time",
                    },
                    "party_size": {"type": "integer", "minimum": 1},
                },
                "required": ["reservation_time", "party_size"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_alternative_slots",
            "description": "Suggest nearby available reservation times when the requested slot is unavailable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_time": {
                        "type": "string",
                        "format": "date-time",
                    },
                    "party_size": {"type": "integer", "minimum": 1},
                },
                "required": ["reservation_time", "party_size"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reservation",
            "description": "Create reservation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "customer_phone": {"type": "string"},
                    "customer_email": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "reservation_time": {"type": "string"},
                    "special_requests": {"type": "string"},
                },
                "required": [
                    "customer_name",
                    "customer_phone",
                    "party_size",
                    "reservation_time",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_reservation",
            "description": "Update an existing reservation's date/time, party size, customer details, or special requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {"type":"string"},
                    "customer_name": {"type": "string"},
                    "customer_phone": {"type": "string"},
                    "customer_email": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "reservation_time": {"type": "string"},
                    "special_requests": {"type": "string"},
                },
                "required": ["reservation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reservation",
            "description": "Cancel reservation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {"type": "string"},
                },
                "required": ["reservation_id"],
            },
        },
    },
]


class AIService:

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        reservation_service: ReservationService,
        restaurant_repo: RestaurantRepository,
    ) -> None:
        self.conversation_repo = conversation_repo
        self.reservation_service = reservation_service
        self.restaurant_repo = restaurant_repo

        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
        )

    async def handle_message(
        self, 
        session_id: str | None, 
        user_message: str,
        restaurant_id: uuid.UUID | None = None,
    ) -> tuple[str, str, uuid.UUID | None]:

        if session_id is None:
            session_id = uuid.uuid4().hex

        conversation, _ = await self.conversation_repo.get_or_create(session_id)
        await self.conversation_repo.touch(conversation)

        # FIX: enum corretto
        await self.conversation_repo.add_message(
            conversation.id,
            'user',   # "user" OK
            user_message
        )

        memory = await self.conversation_repo.get_recent_messages(
            conversation.id,
            settings.CONVERSATION_HISTORY_LIMIT
        )

        restaurant_name = settings.RESTAURANT_NAME
        timezone_name = settings.RESTAURANT_TIMEZONE
        opening_hour = settings.OPENING_HOUR
        closing_hour = settings.CLOSING_HOUR

        if restaurant_id is not None:
            restaurant = await self.restaurant_repo.get_by_id(restaurant_id)

            if restaurant is not None:
                restaurant_name = restaurant.name
                timezone_name = restaurant.timezone
                opening_hour = restaurant.opening_hour
                closing_hour = restaurant.closing_hour

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": _build_system_prompt(
                    restaurant_name,
                    timezone_name,
                    opening_hour,
                    closing_hour,
                ),
            }
        ]

        for msg in memory:
            messages.append(
                {"role": msg.role, "content": msg.content}
            )

        reply, reservation_id = await self._run_completion_loop(
            messages,
            restaurant_id,
            session_id,
        )

        await self.conversation_repo.add_message(
            conversation.id,
            'assistant',
            reply
        )

        return session_id, reply, reservation_id

    async def _run_completion_loop(
        self,
        messages: list[dict[str, Any]],
        restaurant_id: uuid.UUID | None = None,
        session_id: str | None = None,
    ) -> tuple[str, uuid.UUID | None]:

        reservation_id: uuid.UUID | None = None

        for _ in range(5):

            try:
                response = await self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                )
            except OpenAIError as e:
                raise AIServiceError(str(e))

            msg = response.choices[0].message

            if not msg.tool_calls:
                return msg.content or "", reservation_id

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            for tc in msg.tool_calls:
                result, rid = await self._execute_tool(
                    tc.function.name,
                    tc.function.arguments,
                    restaurant_id,
                    session_id,
                )

                if rid:
                    reservation_id = rid

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

        return "Error: tool loop limit reached", reservation_id

    async def _execute_tool(
        self,
        name: str,
        raw_arguments: str,
        restaurant_id: uuid.UUID | None = None,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], uuid.UUID | None]:

        args = json.loads(raw_arguments or "{}")

        try:
            if name == "check_availability":
                ok = await self.reservation_service.check_availability(
                    reservation_time=datetime.fromisoformat(
                        args["reservation_time"].replace("Z", "+00:00")
                    ),
                    party_size=int(args["party_size"]),
                )
                return {"available": ok}, None
            
            if name == "suggest_alternative_slots":
                slots = await self.reservation_service.suggest_alternative_slots(
                    reservation_time=datetime.fromisoformat(
                        args["reservation_time"].replace("Z", "+00:00")
                    ),
                    party_size=int(args["party_size"]),
                    restaurant_id=restaurant_id,
                )

                return {
                    "suggestions": [slot.isoformat() for slot in slots]
                }, None

            if name == "create_reservation":
                payload = ReservationCreate(
                    restaurant_id=restaurant_id,
                    customer_name=args["customer_name"],
                    customer_phone=args["customer_phone"],
                    customer_email=args.get("customer_email"),
                    party_size=int(args["party_size"]),
                    reservation_time=datetime.fromisoformat(
                        args["reservation_time"].replace("Z", "+00:00")
                    ),
                    special_requests=args.get("special_requests"),
                )

                payload.session_id = session_id

                res = await self.reservation_service.create_reservation(payload)

                return {
                    "success": True,
                    "reservation_id": str(res.id)
                }, res.id
            if name == "update_reservation":
                reservation = await self.reservation_service.update_reservation(
                    reservation_id=uuid.UUID(args["reservation_id"]),
                    payload=ReservationUpdate(
                        customer_name=args.get("customer_name"),
                        customer_phone=args.get("customer_phone"),
                        customer_email=args.get("customer_email"),
                        party_size=args.get("party_size"),
                        reservation_time=(
                            datetime.fromisoformat(
                                args["reservation-time"].replace("Z", "+00:00")
                            )
                            if args.get("reservation_time")
                            else None
                        ),
                        special_requests=args.get("special_requests"),
                    ),
                )

                return {
                    "success": True,
                    "reservation_id": str(reservation.id),
                }, reservation.id
            
            if name == "cancel_reservation":
                res = await self.reservation_service.cancel_reservation(
                    uuid.UUID(args["reservation_id"])
                )

                return {"success": True}, None

            return {"error": "unknown tool"}, None

        except Exception as e:
            return {"error": str(e)}, None