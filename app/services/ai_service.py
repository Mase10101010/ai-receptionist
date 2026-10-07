"""
AI service â€” OpenAI integration with conversation memory and function calling.
"""

import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from app.services.reservation_service import (
    BookingAvailabilityOutcome,
    ReservationService,
    _format_reservation_time_for_language,
)

from openai import AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.core.exceptions import AIServiceError, ConflictError
from app.core.logging import get_logger
from app.models.conversation import MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.reservation import ReservationCreate, ReservationUpdate


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
  â€¢ Greet guests warmly and professionally.
  â€¢ Always reply in the same language used by the guest.
  â€¢ If the guest switches language, adapt automatically.
  â€¢ Keep responses natural and localized for the guest language.
  â€¢ Answer questions about hours, location, menu themes, and policies.
  â€¢ Help guests make, modify, or cancel reservations using the tools provided.
  â€¢ Be concise but friendly. Confirm details before creating a reservation.

Restaurant details:
  â€¢ Name: {restaurant_name}
  â€¢ Timezone: {timezone_name}
  â€¢ Hours: {opening_hour:02d}:00 - {closing_hour:02d}:00 daily
  â€¢ Maximum party size handled online: {settings.MAX_PARTY_SIZE}
  â€¢ For larger parties, ask the guest to call directly.

Communication rules:
  â€¢ Never mention you are AI unless explicitly asked.
  â€¢ Match the guest language automatically.
  â€¢ Use localized date/time phrasing depending on the language.

Reservation rules:
  â€¢ Always collect first name, last name, phone number, email, party size, and date/time before booking.
  â€¢ Date, exact reservation time, and party size are required customer-intent fields. Never invent, infer, default, or silently complete a missing required field.
  â€¢ A calendar date without a time does not authorize choosing a time. Ask the guest what time they want.
  â€¢ A time without a calendar date does not authorize choosing a date. Ask the guest which date they want.
  â€¢ A date and time without a party size does not authorize assuming a party size. Ask how many guests.
  â€¢ Never use the restaurant opening time, closing time, availability-window boundary, current time, or any other internal/default value as if the guest selected it.
  â€¢ A broad daypart such as breakfast, lunch, afternoon, dinner, or evening is not an exact booking time. Use it only to help offer suitable times; do not create a reservation until the guest selects or explicitly accepts an exact time.
  â€¢ Approximate times such as "around 7pm" are guest-provided time intent and may be used to search around that time. If an alternative exact time is offered, create the reservation only after the guest explicitly accepts that exact alternative.
  â€¢ The guest must provide both first name and last name. If they provide only one name, politely ask for the missing part before booking.
  â€¢ For reservation tools, customer_provided_date, customer_provided_time, and customer_provided_party_size describe provenance, not whether the tool has a syntactically valid value.
  â€¢ Set a customer_provided_* field to true only when that booking component was explicitly stated by the guest in the conversation or explicitly accepted by the guest after you proposed it.
  â€¢ Never set a customer_provided_* field to true merely because you inferred, defaulted, calculated, or generated the corresponding value yourself.
  â€¢ Before creating the reservation, ask whether the guest has any special requests, allergies, seating preferences, or notes. If they have none, continue with an empty special_requests value.
  â€¢ Email is required because guests receive their reservation confirmation by email.
  â€¢ Interpret all guest-provided dates and times in the restaurant timezone.
  â€¢ Before confirming a slot, call check_availability.
  â€¢ check_availability may return booking_outcome=direct_available, reoptimization_available, live_service_approval_required, or unavailable.
  â€¢ direct_available means the booking can be confirmed immediately.
  â€¢ reoptimization_available means Alias found a safe way to accommodate the request by reorganizing the room, but the request still requires the restaurant's approval unless Alias is authorized to execute it automatically. Never describe this state as confirmed.
  • live_service_approval_required means an already seated reservation requires an explicit live-service operation before its physical table assignment may change. Never describe the requested physical move as already applied.
  â€¢ If booking_outcome is unavailable, call suggest_alternative_slots and offer nearby directly bookable times.
  â€¢ After create_reservation, inspect the returned status. If status is pending, tell the guest that the request was received and is awaiting final confirmation from the restaurant. If status is confirmed, share the reservation id and recap it as confirmed.
  â€¢ Guests may update existing reservations by providing their reservation id.
  â€¢ To modify or cancel a reservation, always ask for the reservation id first.
  â€¢ Never call update_reservation immediately after receiving a reservation id.
  â€¢ After identifying the reservation, ask the guest what they would like to change.
  â€¢ Only call update_reservation when at least one field has been explicitly changed by the guest (date/time, party size, name, phone, email, or special requests).
  â€¢ If no change has been specified, continue the conversation and ask for the desired modification.
  â€¢ When the guest provides a reservation id for modification or cancellation, first call get_reservation.
  â€¢ After retrieving the reservation, mention the guest name linked to that reservation and ask what they would like to modify or confirm cancellation.
  â€¢ Never call update_reservation immediately after receiving only a reservation id.
  â€¢ When checking availability for a modification to an existing reservation, include that reservation's reservation_id in check_availability.
  â€¢ If check_availability returns booking_outcome=reoptimization_available for a modification, you MUST call update_reservation with the guest's requested modification. The availability check is read-only and does not register a pending modification request.
  • If check_availability returns booking_outcome=live_service_approval_required for a modification, you MUST call update_reservation with the guest's requested modification. The availability check is read-only and does not register a pending live-service modification request.
  • Do not tell the guest that the live-service modification request has been received or is awaiting approval until update_reservation returns modification_status=pending.
  • If update_reservation returns booking_outcome=live_service_approval_required and modification_status=pending, the requested physical change has NOT been applied yet. The reservation remains seated on its current physical table assignment until explicit manager approval.
  • Do not tell the guest that the physical table move has already happened.
  â€¢ Do not tell the guest that the modification request has been received or is awaiting approval until update_reservation returns modification_status=pending.
  â€¢ When suggesting alternative times for a modification, include that same reservation_id in suggest_alternative_slots.
  â€¢ An alternative offered for a modification must be validated as a modification of the existing reservation, not as a new competing reservation.
  â€¢ If the guest explicitly accepts an offered alternative time, use that exact time in update_reservation. The backend will revalidate it before changing the existing reservation.
  â€¢ Never create a second reservation to implement a modification.
  â€¢ If update_reservation returns booking_outcome=reoptimization_available and modification_status=pending, the requested modification has NOT been applied yet. Tell the guest that the restaurant has received the modification request and that it is awaiting final approval.
  â€¢ In that state, the guest's existing reservation remains confirmed and unchanged until the restaurant successfully applies the modification.
  â€¢ Never describe a pending modification request as confirmed, completed, or already changed.
  â€¢ After booking_outcome=reoptimization_available for a modification, do NOT call suggest_alternative_slots unless the guest explicitly asks to consider different times instead.
  â€¢ If update_reservation returns error=modification_unavailable, the existing reservation is still unchanged and valid.
  â€¢ After error=modification_unavailable, you MUST call suggest_alternative_slots using the reservation_id returned by update_reservation and the requested reservation_time and party_size. Do not stop at a generic unavailable message and do not tell the guest to contact the restaurant before checking alternatives.
  â€¢ Offer only the alternative times returned by suggest_alternative_slots. Never invent, infer, or reuse an alternative that was not returned by that tool call.
  â€¢ If no year is provided, assume current or next occurrence.

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
                    "reservation_local_datetime": {
                        "type": "string",
                        "description": (
                            "Exact restaurant-local wall-clock date and time explicitly stated "
                            "or explicitly accepted by the guest, formatted as "
                            "YYYY-MM-DDTHH:MM:SS. Copy the guest's intended local clock time "
                            "exactly. Do NOT convert it to UTC, do NOT subtract or add the "
                            "restaurant timezone offset, and do NOT include Z or a timezone "
                            "offset. Example: if the guest requests 7 October 2026 at 19:15 "
                            "and the restaurant timezone is Australia/Perth, use "
                            "'2026-10-07T19:15:00'."
                        ),
                    },
                    "party_size": {"type": "integer", "minimum": 1},
                    "reservation_id": {
                        "type": "string",
                        "description": "Existing reservation id when checking a modification. Omit for a new booking.",
                    },
                    "customer_provided_date": {"type": "boolean"},
                    "customer_provided_time": {"type": "boolean"},
                    "customer_provided_party_size": {"type": "boolean"},
                },
                "required": [
                    "reservation_time",
                    "reservation_local_datetime",
                    "party_size",
                    "customer_provided_date",
                    "customer_provided_time",
                    "customer_provided_party_size",
                ],
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
                    "reservation_id": {
                        "type": "string",
                        "description": "Existing reservation id when alternatives are for a modification. Omit for a new booking.",
                    },
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
                    "customer_name": {
                        "type": "string",
                        "description": "Guest full name including both first name and last name.",
                    },
                    "customer_phone": {"type": "string"},
                    "customer_email": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "reservation_time": {"type": "string"},
                    "reservation_local_datetime": {
                        "type": "string",
                        "description": (
                            "Exact restaurant-local wall-clock date and time explicitly stated "
                            "or explicitly accepted by the guest, formatted as "
                            "YYYY-MM-DDTHH:MM:SS. Copy the guest's intended local clock time "
                            "exactly. Do NOT convert it to UTC, do NOT subtract or add the "
                            "restaurant timezone offset, and do NOT include Z or a timezone "
                            "offset. Example: if the guest requests 7 October 2026 at 19:15 "
                            "and the restaurant timezone is Australia/Perth, use "
                            "'2026-10-07T19:15:00'."
                        ),
                    },
                    "customer_provided_date": {"type": "boolean"},
                    "customer_provided_time": {"type": "boolean"},
                    "customer_provided_party_size": {"type": "boolean"},
                    "special_requests": {
                        "type": "string",
                        "description": "Optional guest notes such as allergies, dietary restrictions, seating preferences, celebrations or other requests. Use an empty string if the guest has no special requests."},
                },
                "required": [
                    "reservation_time",
                    "reservation_local_datetime",
                    "party_size",
                    "customer_provided_date",
                    "customer_provided_time",
                    "customer_provided_party_size",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reservation",
            "description": "Retrieve an existing reservation by reservation id before modifying or cancelling it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {"type": "string"},
                },
                "required": ["reservation_id"],
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
                    "reservation_time": {
                        "type": "string",
                        "description": (
                            "Canonical reservation datetime. "
                            "When reservation_time_source='guest_local', also provide "
                            "reservation_local_datetime with the exact restaurant-local "
                            "wall-clock date/time stated or explicitly accepted by the guest."
                        ),
                    },
                    "reservation_local_datetime": {
                        "type": "string",
                        "description": (
                            "Exact restaurant-local wall-clock date/time stated or explicitly "
                            "accepted by the guest, formatted YYYY-MM-DDTHH:MM:SS with NO "
                            "timezone offset and NO timezone arithmetic. "
                            "Use only when reservation_time_source='guest_local'."
                        ),
                    },
                    "reservation_time_source": {
                        "type": "string",
                        "enum": ["guest_local", "backend_alternative"],
                        "description": (
                            "Use 'guest_local' when the guest directly requests a new date/time. "
                            "Use 'backend_alternative' when applying an exact alternative time "
                            "previously returned by Alias; in that case preserve reservation_time "
                            "exactly and do not reinterpret it as a local wall-clock time."
                        ),
                    },
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

def _canonicalize_customer_local_datetime(
    customer_local_datetime: str,
    timezone_name: str,
) -> datetime:
    local_value = datetime.fromisoformat(
        customer_local_datetime.replace("Z", "+00:00")
    )

    if local_value.tzinfo is not None:
        raise ValueError(
            "reservation_local_datetime must be a timezone-naive "
            "restaurant-local wall-clock datetime"
        )

    return local_value.replace(tzinfo=ZoneInfo(timezone_name))

def _missing_required_booking_intent(
    arguments: dict[str, Any],
) -> list[str]:
    missing: list[str] = []

    if arguments.get("customer_provided_date") is not True:
        missing.append("date")

    if arguments.get("customer_provided_time") is not True:
        missing.append("time")

    if arguments.get("customer_provided_party_size") is not True:
        missing.append("party_size")

    return missing


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
    ) -> tuple[str, str, uuid.UUID | None, str | None, str | None]:

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

        reply, reservation_id, reservation_status, modification_status = await self._run_completion_loop(
            messages,
            restaurant_id,
            session_id,
            timezone_name,
        )

        await self.conversation_repo.add_message(
            conversation.id,
            'assistant',
            reply
        )

        return session_id, reply, reservation_id, reservation_status, modification_status

    async def _run_completion_loop(
        self,
        messages: list[dict[str, Any]],
        restaurant_id: uuid.UUID | None = None,
        session_id: str | None = None,
        timezone_name: str | None = None,
    ) -> tuple[str, uuid.UUID | None, str | None, str | None]:

        reservation_id: uuid.UUID | None = None
        reservation_status: str | None = None
        modification_status: str | None = None
        validated_booking_time: str | None = None
        validated_reservation_id: str | None = None
        validated_party_size: int | None = None

        for completion_round in range(5):

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
            logger.info(
                "AI completion round: round=%d has_tool_calls=%s tools=%s arguments=%s content=%r",
                completion_round + 1,
                bool(msg.tool_calls),
                (
                    [tc.function.name for tc in msg.tool_calls]
                    if msg.tool_calls
                    else []
                ),
                (
                    [tc.function.arguments for tc in msg.tool_calls]
                    if msg.tool_calls
                    else []
                ),
                msg.content,
            )

            if not msg.tool_calls:
                return (
                    msg.content or "",
                    reservation_id,
                    reservation_status,
                    modification_status,
                )

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
                if (
                    tc.function.name == "create_reservation"
                    and validated_booking_time is not None
                ):
                    create_args = json.loads(tc.function.arguments or "{}")

                    if (
                        validated_party_size is not None
                        and create_args.get("party_size") != validated_party_size
                    ):
                        result = {
                            "error": "party_size_changed_after_availability_check",
                            "instruction": (
                                "The party size differs from the party size validated "
                                "by check_availability. Do not create the reservation. "
                                "Run check_availability again for the requested party size."
                            ),
                        }
                        rid = None

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(result),
                            }
                        )
                        continue

                    if (
                        create_args.get("reservation_local_datetime") is not None
                        and timezone_name is not None
                    ):
                        create_time = _canonicalize_customer_local_datetime(
                            create_args["reservation_local_datetime"],
                            timezone_name,
                        )

                        if create_time.isoformat() != validated_booking_time:
                            result = {
                                "error": "reservation_time_changed_after_availability_check",
                                "instruction": (
                                    "The reservation time differs from the time validated "
                                    "by check_availability. Do not create the reservation. "
                                    "Run check_availability again for the requested time."
                                ),
                            }
                            rid = None

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps(result),
                                }
                            )
                            continue

                if (
                    tc.function.name == "update_reservation"
                    and validated_booking_time is not None
                ):
                    update_args = json.loads(tc.function.arguments or "{}")

                    if (
                        validated_reservation_id is not None
                        and update_args.get("reservation_id") != validated_reservation_id
                    ):
                        result = {
                            "error": "reservation_changed_after_availability_check",
                            "instruction": (
                                "The reservation differs from the reservation validated "
                                "by check_availability. Do not update the reservation. "
                                "Run check_availability again for this reservation."
                            ),
                        }
                        rid = None
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        })
                        continue

                    if (
                        validated_party_size is not None
                        and update_args.get("party_size") is not None
                        and update_args.get("party_size") != validated_party_size
                    ):
                        result = {
                            "error": "party_size_changed_after_availability_check",
                            "instruction": (
                                "The party size differs from the party size validated "
                                "by check_availability. Do not update the reservation. "
                                "Run check_availability again for the requested party size."
                            ),
                        }
                        rid = None
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        })
                        continue

                    if (
                        update_args.get("reservation_time_source") == "guest_local"
                        and update_args.get("reservation_local_datetime") is not None
                        and timezone_name is not None
                    ):
                        update_time = _canonicalize_customer_local_datetime(
                            update_args["reservation_local_datetime"],
                            timezone_name,
                        )

                        if update_time.isoformat() != validated_booking_time:
                            result = {
                                "error": "reservation_time_changed_after_availability_check",
                                "instruction": (
                                    "The requested modification time differs from the time "
                                    "validated by check_availability. Do not update the "
                                    "reservation. Run check_availability again for the "
                                    "requested time."
                                ),
                            }
                            rid = None

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps(result),
                                }
                            )
                            continue

                raw_arguments = tc.function.arguments

                if (
                    tc.function.name == "suggest_alternative_slots"
                    and validated_booking_time is not None
                ):
                    alternative_args = json.loads(raw_arguments or "{}")

                    alternative_args["reservation_time"] = validated_booking_time

                    if validated_party_size is not None:
                        alternative_args["party_size"] = validated_party_size

                    if validated_reservation_id is not None:
                        alternative_args["reservation_id"] = validated_reservation_id

                    raw_arguments = json.dumps(alternative_args)
                result, rid = await self._execute_tool(
                    tc.function.name,
                    raw_arguments,
                    restaurant_id,
                    session_id,
                    timezone_name=timezone_name,
                )

                if tc.function.name == "check_availability":
                    if result.get("validated_reservation_time") is not None:
                        validated_booking_time = result["validated_reservation_time"]

                    check_args = json.loads(tc.function.arguments or "{}")

                    if check_args.get("reservation_id") is not None:
                        validated_reservation_id = check_args["reservation_id"]

                    if check_args.get("party_size") is not None:
                        validated_party_size = check_args["party_size"]

                if rid:
                    reservation_id = rid

                    status_value = result.get("status")
                    if isinstance(status_value, str):
                        reservation_status = status_value

                    reservation_status_value = result.get("reservation_status")
                    if isinstance(reservation_status_value, str):
                        reservation_status = reservation_status_value

                    modification_status_value = result.get("modification_status")
                    if isinstance(modification_status_value, str):
                        modification_status = modification_status_value

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

        return (
            "Mi dispiace, non riesco a completare la verifica in questo momento. "
            "Puoi provare un altro orario oppure contattare direttamente il ristorante.",
            reservation_id,
            reservation_status,
            modification_status,
        )

    async def _execute_tool(
        self,
        name: str,
        raw_arguments: str,
        restaurant_id: uuid.UUID | None = None,
        session_id: str | None = None,
        timezone_name: str | None = None,
        customer_local_datetime: str | None = None,
    ) -> tuple[dict[str, Any], uuid.UUID | None]:

        args = json.loads(raw_arguments or "{}")


        logger.info(
            "AI tool call: name=%s restaurant_id=%s reservation_id=%s",
            name,
            restaurant_id,
            args.get("reservation_id"),
        )

        if name in {"check_availability", "create_reservation"}:
            missing_intent = _missing_required_booking_intent(args)

            if missing_intent:
                return {
                    "error": "missing_customer_booking_intent",
                    "missing_fields": missing_intent,
                    "instruction": (
                        "Do not infer or default these booking fields. "
                        "Ask the guest to provide the missing information."
                    ),
                }, None


        try:
            if name == "check_availability":
                if (
                    args.get("reservation_local_datetime") is not None
                    and timezone_name is not None
                ):
                    requested_time = _canonicalize_customer_local_datetime(
                        args["reservation_local_datetime"],
                        timezone_name,
                    )
                else:
                    requested_time = datetime.fromisoformat(
                        args["reservation_time"].replace("Z", "+00:00")
                    )
                requested_party_size = int(args["party_size"])
                existing_reservation_id = (
                    uuid.UUID(args["reservation_id"])
                    if args.get("reservation_id")
                    else None
                )

                if existing_reservation_id is not None:
                    outcome = await (
                        self.reservation_service
                        .assess_modification_availability(
                            reservation_time=requested_time,
                            party_size=requested_party_size,
                            restaurant_id=restaurant_id,
                            reservation_id=existing_reservation_id,
                        )
                    )
                else:
                    outcome = await self.reservation_service.assess_booking_availability(
                        reservation_time=requested_time,
                        party_size=requested_party_size,
                        restaurant_id=restaurant_id,
                    )

                logger.info(
                    (
                        "AI availability result: reservation_id=%s "
                        "outcome=%s requested_time=%s party_size=%s"
                    ),
                    existing_reservation_id,
                    outcome.value,
                    requested_time.isoformat(),
                    requested_party_size,
                )

                return {
                    "available": (
                        outcome != BookingAvailabilityOutcome.UNAVAILABLE
                    ),
                    "booking_outcome": outcome.value,
                    "requires_restaurant_confirmation": (
                        outcome
                        in {
                            BookingAvailabilityOutcome.REOPTIMIZATION_AVAILABLE,
                            BookingAvailabilityOutcome.LIVE_SERVICE_APPROVAL_REQUIRED,
                        }
                    ),
                    "validated_reservation_time": requested_time.isoformat(),
                }, None
            
            if name == "suggest_alternative_slots":
                existing_reservation_id = (
                    uuid.UUID(args["reservation_id"])
                    if args.get("reservation_id")
                    else None
                )

                slots = await self.reservation_service.suggest_alternative_slots(
                    reservation_time=datetime.fromisoformat(
                        args["reservation_time"].replace("Z", "+00:00")
                    ),
                    party_size=int(args["party_size"]),
                    restaurant_id=restaurant_id,
                    reservation_id=existing_reservation_id,
                )

                logger.info(
                    (
                        "AI alternative slots result: "
                        "reservation_id=%s count=%d slots=%s"
                    ),
                    existing_reservation_id,
                    len(slots),
                    [slot.isoformat() for slot in slots],
                )

                return {
                    "suggestions": [slot.isoformat() for slot in slots]
                }, None

            if name == "create_reservation":
                if (
                    args.get("reservation_local_datetime") is not None
                    and timezone_name is not None
                ):
                    requested_time = _canonicalize_customer_local_datetime(
                        args["reservation_local_datetime"],
                        timezone_name,
                    )
                else:
                    requested_time = datetime.fromisoformat(
                        args["reservation_time"].replace("Z", "+00:00")
                    )

                payload = ReservationCreate(
                    restaurant_id=restaurant_id,
                    customer_name=args["customer_name"],
                    customer_phone=args["customer_phone"],
                    customer_email=args.get("customer_email"),
                    party_size=int(args["party_size"]),
                    reservation_time=requested_time,
                    special_requests=args.get("special_requests"),
                )

                payload.session_id = session_id

                res = await self.reservation_service.create_reservation(payload)

                return {
                    "success": True,
                    "reservation_id": str(res.id),
                    "status": res.status.value,
                    "booking_outcome": (
                        BookingAvailabilityOutcome.DIRECT_AVAILABLE.value
                        if res.status.value == "confirmed"
                        else BookingAvailabilityOutcome.REOPTIMIZATION_AVAILABLE.value
                    ),
                    "customer_name": res.customer_name,
                    "customer_email": res.customer_email,
                    "customer_phone": res.customer_phone,
                    "party_size": res.party_size,
                    "reservation_time": res.reservation_time.isoformat(),
                    "special_requests": res.special_requests,
                }, res.id
            if name == "get_reservation":
                reservation = await self.reservation_service.get_reservation(
                    reservation_id=uuid.UUID(args["reservation_id"]),
                    restaurant_id=restaurant_id,
                )

                restaurant_timezone = "UTC"
                restaurant_language = "en"

                if restaurant_id is not None:
                    restaurant = await self.restaurant_repo.get_by_id(restaurant_id)

                    if restaurant is not None:
                        restaurant_timezone = restaurant.timezone or "UTC"
                        restaurant_language = restaurant.preferred_language or "en"

                try:
                    localized_time = reservation.reservation_time.astimezone(
                        ZoneInfo(restaurant_timezone)
                    )
                except Exception:
                    localized_time = reservation.reservation_time

                return {
                    "success": True,
                    "reservation_id": str(reservation.id),
                    "customer_name": reservation.customer_name,
                    "customer_email": reservation.customer_email,
                    "customer_phone": reservation.customer_phone,
                    "party_size": reservation.party_size,
                    "reservation_time": reservation.reservation_time.isoformat(),
                    "reservation_time_local": _format_reservation_time_for_language(
                        localized_time,
                        restaurant_language,
                    ),
                    "timezone": restaurant_timezone,
                    "special_requests": reservation.special_requests,
                    "status": reservation.status.value,
                }, None

            if name == "update_reservation":

                if (
                    args.get("reservation_time_source") == "guest_local"
                    and args.get("reservation_time") is not None
                    and args.get("reservation_local_datetime") is None
                ):
                    return {
                        "error": (
                            "reservation_local_datetime is required when "
                            "reservation_time_source='guest_local'"
                        )
                    }, None
                update_data = {}

                if args.get("customer_name") is not None:
                    update_data["customer_name"] = args["customer_name"]
                
                if args.get("customer_phone") is not None:
                    update_data["customer_phone"] = args["customer_phone"]

                if args.get("customer_email") is not None:
                    update_data["customer_email"] = args["customer_email"]
                
                if args.get("party_size") is not None:
                    update_data["party_size"] = int(args['party_size'])
                
                if args.get("reservation_time") is not None:
                    if (
                        args.get("reservation_time_source") == "guest_local"
                        and args.get("reservation_local_datetime") is not None
                        and timezone_name is not None
                    ):
                        update_data["reservation_time"] = (
                            _canonicalize_customer_local_datetime(
                                args["reservation_local_datetime"],
                                timezone_name,
                            )
                        )
                    else:
                        update_data["reservation_time"] = datetime.fromisoformat(
                            args["reservation_time"].replace("Z", "+00:00")
                        )

                if args.get("special_requests") is not None:
                    update_data["special_requests"] = args["special_requests"]

                if not update_data:
                    return {
                        "error": "No modification details provided."
                    }, None
                
                

                try:
                    reservation = await self.reservation_service.update_reservation(
                        reservation_id=uuid.UUID(args["reservation_id"]),
                        payload=ReservationUpdate(**update_data),
                    )
                except ConflictError:
                    requested_reservation_id = uuid.UUID(
                        args["reservation_id"]
                    )

                    requested_time = update_data.get(
                        "reservation_time"
                    )
                    requested_party_size = update_data.get(
                        "party_size"
                    )

                    logger.info(
                        (
                            "AI direct reservation modification unavailable: "
                            "reservation_id=%s reservation_time=%s "
                            "party_size=%s"
                        ),
                        requested_reservation_id,
                        (
                            requested_time.isoformat()
                            if requested_time is not None
                            else None
                        ),
                        requested_party_size,
                    )

                    authoritative_reservation = await (
                        self.reservation_service.get_reservation(
                            reservation_id=requested_reservation_id,
                            restaurant_id=restaurant_id,
                        )
                    )

                    if (
                        authoritative_reservation.status.value == "seated"
                        and requested_time is not None
                    ):
                        logger.info(
                            (
                                "AI seated reservation time change rejected: "
                                "restaurant_id=%s reservation_id=%s "
                                "requested_time=%s"
                            ),
                            restaurant_id,
                            requested_reservation_id,
                            requested_time.isoformat(),
                        )

                        return {
                            "success": False,
                            "error": "live_seated_time_change_unavailable",
                            "booking_outcome": "unavailable",
                            "reservation_id": str(
                                requested_reservation_id
                            ),
                            "reservation_status": "seated",
                            "requested_reservation_time": (
                                requested_time.isoformat()
                            ),
                            "requested_party_size": (
                                requested_party_size
                            ),
                            "instruction": (
                                "The reservation is already seated. "
                                "Its reservation time cannot be changed "
                                "through reservation reoptimization. "
                                "Keep the current seated reservation and "
                                "physical table assignment unchanged."
                            ),
                        }, None
                    if (
                        authoritative_reservation.status.value == "seated"
                        and requested_party_size is not None
                        and requested_time is None
                    ):
                        live_suggestion = await (
                            self.reservation_service
                            .propose_live_seated_modification(
                                reservation_id=requested_reservation_id,
                                requested_party_size=requested_party_size,
                            )
                        )

                        if live_suggestion is not None:
                            logger.info(
                                (
                                    "AI live seated modification "
                                    "requires approval: "
                                    "restaurant_id=%s reservation_id=%s "
                                    "suggestion_id=%s"
                                ),
                                restaurant_id,
                                requested_reservation_id,
                                live_suggestion.id,
                            )

                            return {
                                "success": True,
                                "booking_outcome": (
                                    "live_service_approval_required"
                                ),
                                "modification_status": "pending",
                                "modification_applied": False,
                                "reservation_status": "seated",
                                "requires_restaurant_confirmation": True,
                                "reservation_id": str(
                                    requested_reservation_id
                                ),
                                "suggestion_id": str(
                                    live_suggestion.id
                                ),
                                "requested_reservation_time": None,
                                "requested_party_size": (
                                    requested_party_size
                                ),
                                "instruction": (
                                    "The requested party-size change "
                                    "has not been applied yet. The "
                                    "party is currently seated and the "
                                    "change requires an explicit "
                                    "live-service reassignment approved "
                                    "by the restaurant. Keep the current "
                                    "physical table assignment unchanged "
                                    "until that action succeeds. Do not "
                                    "describe the modification as already "
                                    "applied or confirmed."
                                ),
                            }, requested_reservation_id

                        return {
                            "success": False,
                            "error": "live_seated_modification_unavailable",
                            "booking_outcome": "unavailable",
                            "reservation_id": str(
                                requested_reservation_id
                            ),
                            "reservation_time": None,
                            "party_size": requested_party_size,
                            "reservation_status": "seated",
                            "instruction": (
                                "The seated party cannot be safely "
                                "reassigned for the requested party-size "
                                "change. Keep the reservation and current "
                                "physical table assignment unchanged."
                            ),
                        }, None

                    suggestion = await (
                        self.reservation_service
                        .propose_reservation_modification_reoptimization(
                            reservation_id=requested_reservation_id,
                            payload=ReservationUpdate(
                                **update_data
                            ),
                        )
                    )

                    if suggestion is not None:
                        logger.info(
                            (
                                "AI reservation modification "
                                "reoptimization available: "
                                "restaurant_id=%s reservation_id=%s "
                                "suggestion_id=%s"
                            ),
                            restaurant_id,
                            requested_reservation_id,
                            suggestion.id,
                        )

                        return {
                            "success": True,
                            "booking_outcome": (
                                "reoptimization_available"
                            ),
                            "modification_status": "pending",
                            "modification_applied": False,
                            "reservation_status": "confirmed",
                            "requires_restaurant_confirmation": True,
                            "reservation_id": str(
                                requested_reservation_id
                            ),
                            "suggestion_id": str(
                                suggestion.id
                            ),
                            "requested_reservation_time": (
                                requested_time.isoformat()
                                if requested_time is not None
                                else None
                            ),
                            "requested_party_size": (
                                requested_party_size
                            ),
                            "instruction": (
                                "The requested modification has not "
                                "been applied yet. Alias found a "
                                "reoptimization plan and the "
                                "modification request is awaiting "
                                "restaurant approval. The existing "
                                "reservation remains confirmed and "
                                "unchanged until the restaurant "
                                "approves and successfully applies "
                                "the modification. Do not call "
                                "suggest_alternative_slots and do "
                                "not describe the modification as "
                                "confirmed."
                            ),
                        }, requested_reservation_id

                    logger.info(
                        (
                            "AI reservation modification unavailable: "
                            "reservation_id=%s reservation_time=%s "
                            "party_size=%s"
                        ),
                        requested_reservation_id,
                        (
                            requested_time.isoformat()
                            if requested_time is not None
                            else None
                        ),
                        requested_party_size,
                    )

                    return {
                        "success": False,
                        "error": "modification_unavailable",
                        "booking_outcome": "unavailable",
                        "reservation_id": str(
                            requested_reservation_id
                        ),
                        "reservation_time": (
                            requested_time.isoformat()
                            if requested_time is not None
                            else None
                        ),
                        "party_size": requested_party_size,
                        "instruction": (
                            "The requested modification is not "
                            "directly available and no safe "
                            "reoptimization plan is available. "
                            "Keep the existing reservation "
                            "unchanged and call "
                            "suggest_alternative_slots with this "
                            "reservation_id, reservation_time, "
                            "and party_size."
                        ),
                    }, None

                return {
                    "success": True,
                    "reservation_id": str(reservation.id),
                    "updated_time": reservation.reservation_time.isoformat(),
                    "party_size": reservation.party_size,
                    "status": reservation.status.value,
                }, reservation.id
            
            if name == "cancel_reservation":
                res = await self.reservation_service.cancel_reservation(
                    uuid.UUID(args["reservation_id"])
                )

                return {"success": True}, None

            return {"error": "unknown tool"}, None

        except Exception as e:
            logger.exception(
                "AI tool execution failed: name=%s restaurant_id=%s reservation_id=%s",
                name,
                restaurant_id,
                args.get("reservation_id"),
            )
            return {"error": str(e)}, None



