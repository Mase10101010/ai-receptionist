import resend

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY


class EmailService:

    async def send_restaurant_welcome_email(
        self,
        to_email: str,
        restaurant_name: str,
        language: str = "en",
    ) -> None:

        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY missing - skipping welcome email")
            return
        content = {
            "en": {
                "subject": "Welcome to Alias",
                "title": "Welcome to Alias.",
                "body": f"{restaurant_name} is now ready. Your AI concierge has been configured and is prepared to help manage reservations, availability and guest communication 24/7.",
                "footer": "Thank you for choosing Alias.",
            },
            "it": {
                "subject": "Benvenuto in Alias",
                "title": "Benvenuto in Alias.",
                "body": f"{restaurant_name} è ora pronto. Il tuo concierge AI è stato configurato ed è pronto ad aiutarti a gestire prenotazioni, disponibilità e comunicazione con gli ospiti 24/7.",
                "footer": "Grazie per aver scelto Alias.",
            },
            "es": {
                "subject": "Bienvenido a Alias",
                "title": "Bienvenido a Alias.",
                "body": f"{restaurant_name} ya está listo. Tu concierge AI ha sido configurado y está preparado para ayudarte a gestionar reservas, disponibilidad y comunicación con clientes 24/7.",
                "footer": "Gracias por elegir Alias.",
            },
            "fr": {
                "subject": "Bienvenue sur Alias",
                "title": "Bienvenue sur Alias.",
                "body": f"{restaurant_name} est maintenant prêt. Votre concierge AI a été configuré et peut vous aider à gérer les réservations, les disponibilités et la communication client 24/7.",
                "footer": "Merci d’avoir choisi Alias.",
            },
            "de": {
                "subject": "Willkommen bei Alias",
                "title": "Willkommen bei Alias.",
                "body": f"{restaurant_name} ist jetzt bereit. Dein AI-Concierge wurde eingerichtet und hilft dir dabei, Reservierungen, Verfügbarkeit und Gästekommunikation rund um die Uhr zu verwalten.",
                "footer": "Danke, dass du Alias gewählt hast.",
            },
        }
        text = content.get(language, content["en"])
        try:
            resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": [to_email],
                    "subject": text["subject"],
                    "html": f"""
                    <div style="background:#0b0b0b;padding:40px 20px;font-family:Arial,sans-serif;color:white;">
                        <div style="max-width:600px;margin:0 auto;background:#111111;border:1px solid #222;border-radius:20px;overflow:hidden;">
                            <div style="padding:40px 20px;text-align:center;background:black;">
                                <img
                                    src="https://www.aliasconcierge.com/alias-logo-dark.png"
                                    alt="Alias"
                                    style="max-width:260px;width:100%;"
                                />
                            </div>

                            <div style="padding:40px;">
                                <h1 style="margin-top:0;font-size:28px;color:white;">
                                    {text["title"]}
                                </h1>

                                <p style="color:#cccccc;font-size:16px;line-height:1.7;">
                                    {text["body"]}
                                </p>

                                <div style="margin:30px 0;padding:24px;background:#181818;border-radius:16px;border:1px solid #2a2a2a;">
                                    <p style="margin:0;color:#cccccc;">
                                        <strong style="color:white;">Restaurant:</strong><br>
                                        {restaurant_name}
                                    </p>
                                </div>

                                <p style="color:#aaaaaa;font-size:14px;line-height:1.7;">
                                    {text["footer"]}
                                </p>

                                <p style="margin-top:40px;color:#cccccc;font-size:15px;">
                                    The Alias Team
                                </p>
                            </div>
                        </div>
                    </div>
                    """,
                }
            )
        except Exception as e:
            logger.exception(
                "Failed to send restaurant welcome email: %s",
                e,
            )

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

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_link: str,
    ) -> None:

        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY missing - skipping email")
            return

        try:
            resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": [to_email],
                    "subject": "Reset your Alias password",
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

                                <h1 style="color:white;">
                                    Reset your password
                                </h1>

                                <p style="color:#cccccc;line-height:1.7;">
                                    We received a request to reset your password.
                                </p>

                                <div style="margin:40px 0;text-align:center;">
                                    <a
                                        href="{reset_link}"
                                        style="
                                            background:white;
                                            color:black;
                                            padding:14px 24px;
                                            border-radius:12px;
                                            text-decoration:none;
                                            font-weight:bold;
                                        "
                                    >
                                        Reset Password
                                    </a>
                                </div>

                                <p style="color:#888888;font-size:14px;">
                                    This link expires in 30 minutes.
                                </p>

                            </div>
                        </div>
                    </div>
                    """,
                }
            )

            logger.info(
                "Sending reservation confirmation email to %s",
                to_email,
            )

        except Exception as e:
            logger.exception("Failed to send reset email: %s", e)