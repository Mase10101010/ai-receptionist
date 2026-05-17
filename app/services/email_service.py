import resend

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY


class EmailService:

    async def send_reservation_confirmation(
        self,
        to_email: str,
        restaurant_name: str,
        customer_name: str,
        reservation_id: str,
        reservation_time: str,
        party_size: int,
    ) -> None:

        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY missing - skipping email")
            return

        try:
            resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": [to_email],
                    "subject": f"{restaurant_name} Reservation Confirmation",
                    "html": f"""
                    <div style="font-family:Arial;padding:24px;">
                        <h2>Reservation confirmed</h2>

                        <p>Hello {customer_name},</p>

                        <p>Your reservation has been confirmed.</p>

                        <ul>
                            <li><strong>Restaurant:</strong> {restaurant_name}</li>
                            <li><strong>Date & Time:</strong> {reservation_time}</li>
                            <li><strong>Party Size:</strong> {party_size}</li>
                            <li><strong>Reservation ID:</strong> {reservation_id}</li>
                        </ul>

                        <p>Please keep your reservation ID for modifications or cancellations.</p>

                        <p>We look forward to welcoming you.</p>
                    </div>
                    """,
                }
            )

        except Exception as e:
            logger.exception("Failed to send confirmation email: %s", e)