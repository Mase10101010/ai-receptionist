import stripe

from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:

    @staticmethod
    def create_checkout_session(
        customer_email: str,
        success_url: str,
        cancel_url: str,
        user_id: str,
        use_trial: bool = True,
    ):
        subscription_data={}

        if use_trial:
            subscription_data["trial_period_days"] = settings.STRIPE_TRIAL_DAYS

        return stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            customer_email=customer_email,
            metadata={
                "user_id": user_id,
            },
            line_items=[
                {
                    "price": settings.STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ],
            subscription_data=subscription_data,
            success_url=success_url,
            cancel_url=cancel_url,
            locale="auto",
        )
    
    @staticmethod
    def create_customer_portal_session(
        customer_id: str,
        return_url: str,
    ):
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )