from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.db.session import get_db

from app.models.reservation import ReservationStatus

from app.intelligence_execution.gate import (
    IntelligenceExecutionGate,
)
from app.services.reservation_service import (
    _format_reservation_time_for_language,
)

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_events.service import (
    IntelligenceEventService,
)

from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)
from app.repositories.reservation_repository import (
    ReservationRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)

from app.services.ai_suggestion_service import (
    AISuggestionService,
)
from app.services.email_service import EmailService

from app.intelligence_events.schemas import (
    IntelligenceEventResponse,
)

from app.intelligence_execution.orchestrator import (
    IntelligenceExecutionOrchestrator,
)

from .schemas import (
    IntelligenceApplyRequest,
    IntelligenceApplyResponse,
    IntelligenceOptimizeRequest,
    IntelligenceOptimizeResponse,
    IntelligenceReoptimizeRequest,
    IntelligenceReoptimizeResponse,
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
)
from .sqlalchemy_service import (
    IntelligenceOptimizationService,
)


router = APIRouter(
    prefix="/intelligence",
    tags=["intelligence"],
)

service = IntelligenceOptimizationService()

logger = get_logger(__name__)


@router.post(
    "/optimize",
    response_model=IntelligenceOptimizeResponse,
)
async def optimize_reservation(
    payload: IntelligenceOptimizeRequest,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceOptimizeResponse:
    return await service.optimize(
        session=session,
        payload=payload,
    )


@router.post(
    "/reoptimize",
    response_model=IntelligenceReoptimizeResponse,
)
async def reoptimize_reservation(
    payload: IntelligenceReoptimizeRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceReoptimizeResponse:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = {
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    }

    if (
        payload.restaurant_id
        not in allowed_restaurant_ids
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Restaurant not found",
        )

    return await service.reoptimize(
        session=session,
        payload=payload,
    )


@router.post(
    "/apply-reoptimization",
    response_model=(
        IntelligenceApplyReoptimizationResponse
    ),
)
async def apply_reoptimization(
    payload: IntelligenceApplyReoptimizationRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceApplyReoptimizationResponse:
    restaurant_repository = RestaurantRepository(
        session,
    )

    restaurants = await restaurant_repository.list_by_owner(
        current_user.id,
    )

    allowed_restaurant_ids = [
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    ]

    reservation_repository = ReservationRepository(
        session,
    )

    # Capture lifecycle truth before execution.
    # A confirmation email is valid only for a real
    # PENDING -> CONFIRMED transition.
    previous_reservation = (
        await reservation_repository.get_by_id_for_restaurants(
            reservation_id=payload.new_reservation_id,
            restaurant_ids=allowed_restaurant_ids,
        )
    )

    previous_status = (
        previous_reservation.status
        if previous_reservation is not None
        else None
    )

    result = await IntelligenceExecutionOrchestrator(
        intelligence_service=service,
    ).apply_reoptimization(
        session=session,
        payload=payload,
        allowed_restaurant_ids=allowed_restaurant_ids,
        source=IntelligenceEventSource.MANAGER,
        actor_user_id=current_user.id,
    )

    confirmed_reservation = (
        await reservation_repository.get_by_id_for_restaurants(
            reservation_id=payload.new_reservation_id,
            restaurant_ids=allowed_restaurant_ids,
        )
    )

    should_send_confirmation = (
        previous_status == ReservationStatus.PENDING
        and confirmed_reservation is not None
        and confirmed_reservation.status
        == ReservationStatus.CONFIRMED
        and bool(confirmed_reservation.customer_email)
    )

    notification_data = None

    if should_send_confirmation:
        try:
            restaurant = await restaurant_repository.get_by_id(
                confirmed_reservation.restaurant_id
            )

            if restaurant is not None:
                restaurant_timezone = (
                    restaurant.timezone or "UTC"
                )
                restaurant_language = (
                    restaurant.preferred_language or "en"
                )

                try:
                    localized_time = (
                        confirmed_reservation
                        .reservation_time
                        .astimezone(
                            ZoneInfo(restaurant_timezone)
                        )
                    )
                except Exception:
                    logger.exception(
                        "Invalid restaurant timezone: %s. "
                        "Falling back to UTC.",
                        restaurant_timezone,
                    )
                    localized_time = (
                        confirmed_reservation
                        .reservation_time
                        .astimezone(
                            ZoneInfo("UTC")
                        )
                    )

                notification_data = {
                    "to_email": (
                        confirmed_reservation.customer_email
                    ),
                    "restaurant_name": restaurant.name,
                    "customer_name": (
                        confirmed_reservation.customer_name
                    ),
                    "reservation_id": str(
                        confirmed_reservation.id
                    ),
                    "reservation_time": (
                        _format_reservation_time_for_language(
                            localized_time,
                            restaurant_language,
                        )
                    ),
                    "party_size": (
                        confirmed_reservation.party_size
                    ),
                    "language": restaurant_language,
                }

        except Exception:
            logger.exception(
                "Post-reoptimization confirmation "
                "notification preparation failed: "
                "reservation_id=%s",
                payload.new_reservation_id,
            )

    # Database truth must become durable before any external
    # confirmation is sent.
    await session.commit()

    if notification_data is not None:
        try:
            await EmailService().send_reservation_confirmation(
                **notification_data,
            )
        except Exception:
            logger.exception(
                "Post-reoptimization reservation "
                "confirmation email failed: "
                "reservation_id=%s",
                payload.new_reservation_id,
            )

    return result


@router.post(
    "/apply",
    response_model=IntelligenceApplyResponse,
)
async def apply_recommendation(
    payload: IntelligenceApplyRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_db),
) -> IntelligenceApplyResponse:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = [
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    ]

    result = (
        await service.apply_recommendation(
            session=session,
            payload=payload,
            allowed_restaurant_ids=(
                allowed_restaurant_ids
            ),
        )
    )

    await session.commit()

    return result


@router.get(
    "/events",
    response_model=list[IntelligenceEventResponse],
)
async def list_intelligence_events(
    restaurant_id: UUID,
    current_user: CurrentUserDep,
    event_type: IntelligenceEventType | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> list[IntelligenceEventResponse]:
    restaurant_repository = (
        RestaurantRepository(
            session,
        )
    )

    restaurants = (
        await restaurant_repository
        .list_by_owner(
            current_user.id,
        )
    )

    allowed_restaurant_ids = {
        restaurant.id
        for restaurant in restaurants
        if restaurant.subscription_status
        in {
            "active",
            "trialing",
            "lifetime",
        }
    }

    if (
        restaurant_id
        not in allowed_restaurant_ids
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Restaurant not found",
        )

    events = await (
        IntelligenceEventService(
            repository=(
                IntelligenceEventRepository(
                    session,
                )
            ),
        )
        .list_restaurant_events(
            restaurant_id=restaurant_id,
            limit=min(
                max(limit, 1),
                500,
            ),
            offset=max(
                offset,
                0,
            ),
            event_type=event_type,
        )
    )

    return [
        IntelligenceEventResponse
        .model_validate(event)
        for event in events
    ]