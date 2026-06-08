from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.restaurant_repository import RestaurantRepository
from app.services.stripe_service import StripeService

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutSessionRequest(BaseModel):
    success_url: str
    cancel_url: str

class CustomerPortalRequest(BaseModel):
    return_url: str


@router.post("/create-checkout-session")
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    
    restaurant_repo = RestaurantRepository(db)

    restaurants = await restaurant_repo.list_by_owner(
        current_user.id
    )

    if not restaurants:
        raise HTTPException(
            status_code=404,
            detail="No restaurant found for this account",
        )
    
    restaurant = restaurants[0]

    if restaurant.subscription_status == "active":
        raise HTTPException(
            status_code=400,
            detail="Subscription already active",
        )

    if restaurant.subscription_status == "lifetime":
        raise HTTPException(
            status_code=400,
            detail="Lifetime accounts do not require billing",
        )
    
    session = StripeService.create_checkout_session(
        customer_email=current_user.email,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
        use_trial=not restaurant.has_used_trial,
        restaurant_id=str(restaurant.id),
    )

    return {
        "checkout_url": session.url,
        "session_id": session.id,
    }

@router.post("/customer-portal")
async def create_customer_portal(
    payload: CustomerPortalRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    restaurant_repo = RestaurantRepository(db)

    restaurants = await restaurant_repo.list_by_owner(
        current_user.id
    )

    if not restaurants:
        raise HTTPException(
            status_code=404,
            detail="No restaurant found for this account",
        )

    restaurant = restaurants[0]

    if not restaurant.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer found for this account",
        )

    session = StripeService.create_customer_portal_session(
        customer_id=restaurant.stripe_customer_id,
        return_url=payload.return_url,
    )

    return {
        "portal_url": session.url,
    }

@router.get("/status")
async def get_billing_status(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
):
    restaurant_repo = RestaurantRepository(db)

    restaurants = await restaurant_repo.list_by_owner(
        current_user.id
    )

    if not restaurants:
        raise HTTPException(
            status_code=404,
            detail="No restaurant found for this account",
        )

    restaurant = restaurants[0]

    return {
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "subscription_status": restaurant.subscription_status,
        "has_used_trial": restaurant.has_used_trial,
        "trial_start_date": restaurant.trial_start_date,
        "trial_end_date": restaurant.trial_end_date,
        "subscription_start_date": restaurant.subscription_start_date,
        "subscription_end_date": restaurant.subscription_end_date,
        "stripe_customer_id": restaurant.stripe_customer_id,
        "stripe_subscription_id": restaurant.stripe_subscription_id,
    }