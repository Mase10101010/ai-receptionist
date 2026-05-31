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
        language: str = "en",
    ) -> None:

        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY missing - skipping email")
            return
        
        content = {
            "en": {
                "subject": f"{restaurant_name} Reservation Confirmation",
                "title": "Reservation Confirmed",
                "greeting": f"Hello {customer_name},",
                "body": f"Your reservation at {restaurant_name} has been confirmed.",
                "party_label": "Party Size",
                "guest_word": "guests",
                "date_label": "Date & Time",
                "reservation_id_label": "Reservation ID",
                "note": "Please keep your reservation ID for future modifications or cancellations.",
                "footer": "We look forward to welcoming you.",
            },
            "it": {
                "subject": f"Conferma prenotazione {restaurant_name}",
                "title": "Prenotazione confermata",
                "greeting": f"Ciao {customer_name},",
                "body": f"La tua prenotazione presso {restaurant_name} è stata confermata.",
                "party_label": "Numero ospiti",
                "guest_word": "ospiti",
                "date_label": "Data e ora",
                "reservation_id_label": "ID prenotazione",
                "note": "Conserva il tuo ID prenotazione per eventuali modifiche o cancellazioni.",
                "footer": "Non vediamo l'ora di accoglierti.",
            },
            "es": {
                "subject": f"Confirmación de reserva {restaurant_name}",
                "title": "Reserva confirmada",
                "greeting": f"Hola {customer_name},",
                "body": f"Tu reserva en {restaurant_name} ha sido confirmada.",
                "party_label": "Número de personas",
                "guest_word": "personas",
                "date_label": "Fecha y hora",
                "reservation_id_label": "ID de reserva",
                "note": "Conserva tu ID de reserva para futuras modificaciones o cancelaciones.",
                "footer": "Esperamos darte la bienvenida.",
            },
            "fr": {
                "subject": f"Confirmation de réservation {restaurant_name}",
                "title": "Réservation confirmée",
                "greeting": f"Bonjour {customer_name},",
                "body": f"Votre réservation chez {restaurant_name} a été confirmée.",
                "party_label": "Nombre de personnes",
                "guest_word": "personnes",
                "date_label": "Date et heure",
                "reservation_id_label": "ID de réservation",
                "note": "Veuillez conserver votre ID de réservation pour toute modification ou annulation.",
                "footer": "Nous avons hâte de vous accueillir.",
            },
            "de": {
                "subject": f"Reservierungsbestätigung {restaurant_name}",
                "title": "Reservierung bestätigt",
                "greeting": f"Hallo {customer_name},",
                "body": f"Ihre Reservierung bei {restaurant_name} wurde bestätigt.",
                "party_label": "Anzahl Gäste",
                "guest_word": "Gäste",
                "date_label": "Datum & Uhrzeit",
                "reservation_id_label": "Reservierungs-ID",
                "note": "Bitte bewahren Sie Ihre Reservierungs-ID für zukünftige Änderungen oder Stornierungen auf.",
                "footer": "Wir freuen uns auf Ihren Besuch.",
            },
        }

        language = (language or "en").lower()
        text = content.get(language, content["en"])

        try:
            resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": [to_email],
                    "subject": text["subject"],
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
                                    {text["title"]}
                                </h1>

                                <p style="
                                    color:#cccccc;
                                    font-size:16px;
                                    line-height:1.7;
                                ">
                                    {text["greeting"]}
                                </p>

                                <p style="
                                    color:#cccccc;
                                    font-size:16px;
                                    line-height:1.7;
                                ">
                                    {text["body"]}
                                </p>

                                <div style="
                                    margin:30px 0;
                                    padding:24px;
                                    background:#181818;
                                    border-radius:16px;
                                    border:1px solid #2a2a2a;
                                ">

                                    <p><strong>{text["reservation_id_label"]}:</strong><br>{reservation_id}</p>

                                    <p><strong>{text["date_label"]}:</strong><br>{reservation_time}</p>

                                    <p><strong>{text["party_label"]}:</strong><br>{party_size} {text["guest_word"]}</p>

                                </div>

                                <p style="
                                    color:#aaaaaa;
                                    font-size:14px;
                                    line-height:1.7;
                                ">
                                    {text["note"]}
                                </p>

                                <p style="
                                    margin-top:40px;
                                    color:#cccccc;
                                    font-size:15px;
                                ">
                                    {text["footer"]}
                                </p>

                            </div>
                        </div>
                    </div>
                    """,
                }
            )

        except Exception as e:
            logger.exception("Failed to send confirmation email: %s", e)
    
    async def send_restaurant_reservation_notification(
        self,
        restaurant_email: str,
        restaurant_name: str,
        customer_name: str,
        customer_email: str | None,
        customer_phone: str,
        reservation_time: str,
        party_size: int,
        table_number: str | None = None,
        special_requests: str | None = None,
        language: str = "en",
    ) -> None:

        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY missing - skipping restaurant notification email")
            return

        
        language = (language or "en").lower()
        content = {
            "en": {
                "subject": f"New reservation - {restaurant_name}",
                "title": "New reservation received",
                "body": f"A new reservation has been created for {restaurant_name}.",
                "guest_label": "Guest",
                "email_label": "Email",
                "phone_label": "Phone",
                "party_label": "Party size",
                "date_label": "Date & Time",
                "table_label": "Assigned table",
                "table_word": "Table",
                "not_assigned": "Not assigned",
                "notes_label": "Special requests",
                "no_notes": "No special requests",
                "not_provided": "Not provided",
                "footer": "You can view this reservation inside your Alias dashboard.",
            },
            "it": {
                "subject": f"Nuova prenotazione - {restaurant_name}",
                "title": "Nuova prenotazione ricevuta",
                "body": f"È stata creata una nuova prenotazione per {restaurant_name}.",
                "guest_label": "Cliente",
                "email_label": "Email",
                "phone_label": "Telefono",
                "party_label": "Numero ospiti",
                "date_label": "Data e ora",
                "table_label": "Tavolo assegnato",
                "table_word": "Tavolo",
                "not_assigned": "Non assegnato",
                "notes_label": "Richieste speciali",
                "no_notes": "Nessuna richiesta speciale",
                "not_provided": "Non fornita",
                "footer": "Puoi visualizzare questa prenotazione nella dashboard di Alias.",
            },
            "es": {
                "subject": f"Nueva reserva - {restaurant_name}",
                "title": "Nueva reserva recibida",
                "body": f"Se ha creado una nueva reserva para {restaurant_name}.",
                "guest_label": "Cliente",
                "email_label": "Correo electrónico",
                "phone_label": "Teléfono",
                "party_label": "Número de personas",
                "date_label": "Fecha y hora",
                "table_label": "Mesa asignada",
                "table_word": "Mesa",
                "not_assigned": "No asignada",
                "notes_label": "Solicitudes especiales",
                "no_notes": "Sin solicitudes especiales",
                "not_provided": "No proporcionado",
                "footer": "Puedes ver esta reserva en tu panel de Alias.",
            },

            "fr": {
                "subject": f"Nouvelle réservation - {restaurant_name}",
                "title": "Nouvelle réservation reçue",
                "body": f"Une nouvelle réservation a été créée pour {restaurant_name}.",
                "guest_label": "Client",
                "email_label": "Email",
                "phone_label": "Téléphone",
                "party_label": "Nombre de personnes",
                "date_label": "Date et heure",
                "table_label": "Table attribuée",
                "table_word": "Table",
                "not_assigned": "Non attribuée",
                "notes_label": "Demandes spéciales",
                "no_notes": "Aucune demande spéciale",
                "not_provided": "Non fourni",
                "footer": "Vous pouvez consulter cette réservation dans votre tableau de bord Alias.",
            },

            "de": {
                "subject": f"Neue Reservierung - {restaurant_name}",
                "title": "Neue Reservierung erhalten",
                "body": f"Für {restaurant_name} wurde eine neue Reservierung erstellt.",
                "guest_label": "Gast",
                "email_label": "E-Mail",
                "phone_label": "Telefon",
                "party_label": "Anzahl Gäste",
                "date_label": "Datum & Uhrzeit",
                "table_label": "Zugewiesener Tisch",
                "table_word": "Tisch",
                "not_assigned": "Nicht zugewiesen",
                "notes_label": "Besondere Wünsche",
                "no_notes": "Keine besonderen Wünsche",
                "not_provided": "Nicht angegeben",
                "footer": "Sie können diese Reservierung im Alias-Dashboard anzeigen.",
            },
        }

        text = content.get(language, content["en"])

        table_text = (
            f'{text["table_word"]} {table_number}'
            if table_number
            else text["not_assigned"]
        )
        notes_text = special_requests or text["no_notes"]
        customer_email_text = customer_email or text["not_provided"]

        try:
            resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": [restaurant_email],
                    "subject": text["subject"],
                    "html": f"""
                    <div style="background:#0b0b0b;padding:40px 20px;font-family:Arial,sans-serif;color:white;">
                        <div style="max-width:600px;margin:0 auto;background:#111111;border:1px solid #222;border-radius:20px;overflow:hidden;">
                            <div style="padding:40px;">
                                <h1 style="margin-top:0;font-size:28px;color:white;">
                                    {text["title"]}
                                </h1>

                                <p style="color:#cccccc;font-size:16px;line-height:1.7;">
                                    {text["body"]}
                                </p>

                                <div style="margin:30px 0;padding:24px;background:#181818;border-radius:16px;border:1px solid #2a2a2a;">
                                   <p><strong>{text["guest_label"]}:</strong><br>{customer_name}</p>
                                    <p><strong>{text["email_label"]}:</strong><br>{customer_email_text}</p>
                                    <p><strong>{text["phone_label"]}:</strong><br>{customer_phone}</p>
                                    <p><strong>{text["party_label"]}:</strong><br>{party_size}</p>
                                    <p><strong>{text["date_label"]}:</strong><br>{reservation_time}</p>
                                    <p><strong>{text["table_label"]}:</strong><br>{table_text}</p>
                                    <p><strong>{text["notes_label"]}:</strong><br>{notes_text}</p> 
                                </div>

                                <p style="color:#aaaaaa;font-size:14px;line-height:1.7;">
                                    {text["footer"]}
                                </p>
                            </div>
                        </div>
                    </div>
                    """,
                }
            )

        except Exception as e:
            logger.exception(
                "Failed to send restaurant reservation notification email: %s",
                e,
            )

    async def send_email_verification_email(
        self,
        to_email: str,
        verification_link: str,
    ) -> None:

        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY missing - skipping email")
            return

        try:
            resend.Emails.send(
                {
                    "from": settings.EMAIL_FROM,
                    "to": [to_email],
                    "subject": "Verify your Alias account",
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
                                    src="https://www.aliasconcierge.com/alias-logo-dark.png"
                                    alt="Alias"
                                    style="max-width:260px;width:100%;"
                                />
                            </div>

                            <div style="padding:40px;">

                                <h1 style="color:white;">
                                    Verify your email
                                </h1>

                                <p style="color:#cccccc;line-height:1.7;">
                                    Welcome to Alias.
                                    Please verify your email address to activate your account.
                                </p>

                                <div style="margin:40px 0;text-align:center;">
                                    <a
                                        href="{verification_link}"
                                        style="
                                            background:white;
                                            color:black;
                                            padding:14px 24px;
                                            border-radius:12px;
                                            text-decoration:none;
                                            font-weight:bold;
                                        "
                                    >
                                        Verify Account
                                    </a>
                                </div>

                                <p style="color:#888888;font-size:14px;">
                                    This verification link expires in 24 hours.
                                </p>

                            </div>
                        </div>
                    </div>
                    """,
                }
            )

        except Exception as e:
            logger.exception(
                "Failed to send verification email: %s",
                e,
            )

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