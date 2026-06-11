from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
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
    user_repo = UserRepository(db)

    user = await user_repo.get_by_id(current_user.id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.subscription_status == "active":
        raise HTTPException(
            status_code=400,
            detail="Subscription already active",
        )

    if user.subscription_status == "lifetime":
        raise HTTPException(
            status_code=400,
            detail="Lifetime accounts do not require billing",
        )

    session = StripeService.create_checkout_session(
        customer_email=user.email,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
        use_trial=not user.has_used_trial,
        user_id=str(user.id),
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
    user_repo = UserRepository(db)

    user = await user_repo.get_by_id(current_user.id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer found for this account",
        )

    session = StripeService.create_customer_portal_session(
        customer_id=user.stripe_customer_id,
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
    user_repo = UserRepository(db)

    user = await user_repo.get_by_id(current_user.id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {
        "user_id": user.id,
        "email": user.email,
        "subscription_status": user.subscription_status,
        "has_used_trial": user.has_used_trial,
        "trial_start_date": user.trial_start_date,
        "trial_end_date": user.trial_end_date,
        "subscription_start_date": user.subscription_start_date,
        "subscription_end_date": user.subscription_end_date,
        "stripe_customer_id": user.stripe_customer_id,
        "stripe_subscription_id": user.stripe_subscription_id,
    }