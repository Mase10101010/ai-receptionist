from datetime import datetime
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.repositories.restaurant_repository import RestaurantRepository

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)

stripe.api_key = settings.STRIPE_SECRET_KEY


def _ts_to_datetime(value):
    if value is None:
        return None

    return datetime.utcfromtimestamp(value)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid payload",
        )

    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=400,
            detail="Invalid signature",
        )

    event_type = event["type"]
    data = event["data"]["object"]

    print("Stripe event:", event_type)

    if event_type == "checkout.session.completed":
        restaurant_id = data["metadata"]["restaurant_id"]

        if restaurant_id:
            restaurant_repo = RestaurantRepository(db)

            restaurant = await restaurant_repo.get_by_id(
                UUID(restaurant_id)
            )

            if restaurant:
                subscription_id = data["subscription"]
                customer_id = data["customer"]

                subscription = None

                if subscription_id:
                    subscription = stripe.Subscription.retrieve(
                        subscription_id
                    )

                fields = {
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "subscription_status": "active",
                    "has_used_trial": True,
                }

                if subscription:
                    fields["trial_start_date"] = _ts_to_datetime(
                        subscription["trial_start"]
                    )
                    fields["trial_end_date"] = _ts_to_datetime(
                        subscription["trial_end"]
                    )

                    first_item= subscription["items"]["data"][0]

                    fields["subscription_start_date"] = _ts_to_datetime(
                        first_item["current_period_start"]
                    )
                    fields["subscription_end_date"] = _ts_to_datetime(
                        first_item["current_period_end"]
                    )

                await restaurant_repo.update(
                    restaurant,
                    fields,
                )

                await db.commit()
    
    elif event_type == "customer.subscription.deleted":

        subscription_id = data["id"]

        restaurant_repo = RestaurantRepository(db)

        restaurants = await restaurant_repo.list_all()

        for restaurant in restaurants:
            if (
                restaurant.stripe_subscription_id
                == subscription_id
            ):
                await restaurant_repo.update(
                    restaurant,
                    {
                        "subscription_status": "inactive",
                    }
                )

                await db.commit()
                break

    elif event_type == "customer.subscription.updated":
        subscription_id = data["id"]

        restaurant_repo = RestaurantRepository(db)

        restaurants = await restaurant_repo.list_all()

        for restaurant in restaurants:
            if (
                restaurant.stripe_subscription_id
                == subscription_id
            ):
                await restaurant_repo.update(
                    restaurant,
                    {
                        "subscription_status": data["status"],
                    }
                )

                await db.commit()
                break

    return {"received": True}