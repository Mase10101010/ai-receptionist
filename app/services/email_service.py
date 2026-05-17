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
                    <div style="
                        background:#0b0b0b;
                        padding:40px 20px;
                        font-family:Arial,sans-serif;
                        color:white;
                    ">

                        <div style="
                            max-width:600px;
                            margin:0 auto;
                            background:#111111;
                            border:1px solid #222;
                            border-radius:20px;
                            overflow:hidden;
                        ">

                            <div style="
                                padding:40px 20px;
                                text-align:center;
                                background:black;
                            ">
                                <img
                                    src="https://alias-platform.vercel.app/alias-logo-dark.png"
                                    alt="Alias"
                                    style="max-width:260px;width:100%;"
                                />
                            </div>

                            <div style="padding:40px;">

                                <h1 style="
                                    margin-top:0;
                                    font-size:28px;
                                    color:white;
                                ">
                                    Reservation Confirmed
                                </h1>

                                <p style="
                                    color:#cccccc;
                                    font-size:16px;
                                    line-height:1.7;
                                ">
                                    Hello {customer_name},
                                </p>

                                <p style="
                                    color:#cccccc;
                                    font-size:16px;
                                    line-height:1.7;
                                ">
                                    Your reservation at
                                    <strong style="color:white;">
                                        {restaurant_name}
                                    </strong>
                                    has been confirmed.
                                </p>

                                <div style="
                                    margin:30px 0;
                                    padding:24px;
                                    background:#181818;
                                    border-radius:16px;
                                    border:1px solid #2a2a2a;
                                ">

                                    <p><strong>Reservation ID:</strong><br>{reservation_id}</p>

                                    <p><strong>Date & Time:</strong><br>{reservation_time}</p>

                                    <p><strong>Party Size:</strong><br>{party_size} guests</p>

                                </div>

                                <p style="
                                    color:#aaaaaa;
                                    font-size:14px;
                                    line-height:1.7;
                                ">
                                    Please keep your reservation ID for future
                                    modifications or cancellations.
                                </p>

                                <p style="
                                    margin-top:40px;
                                    color:#cccccc;
                                    font-size:15px;
                                ">
                                    We look forward to welcoming you.
                                </p>

                            </div>
                        </div>
                    </div>
                    """,
                }
            )

        except Exception as e:
            logger.exception("Failed to send confirmation email: %s", e)