from app.core.exceptions import ConflictError, ValidationError
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.services.email_service import EmailService
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserCreate, UserLogin


class AuthService:
    def __init__(
        self,
        repository: UserRepository,
        email_service: EmailService,
    ) -> None:
        self.repository = repository
        self.email_service = email_service

    async def register(self, payload: UserCreate) -> tuple[User, str]:
        existing = await self.repository.get_by_email(str(payload.email))

        if existing is not None:
            raise ConflictError("An account with this email already exists")

        user = User(
            email=str(payload.email).lower(),
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            is_active=True,
        )

        created = await self.repository.create(user)

        token = create_access_token(
            subject=str(created.id),
            extra_claims={"email": created.email},
        )

        return created, token

    async def login(self, payload: UserLogin) -> tuple[User, str]:
        user = await self.repository.get_by_email(str(payload.email))

        if user is None:
            raise ValidationError("Invalid email or password")

        if not verify_password(payload.password, user.hashed_password):
            raise ValidationError("Invalid email or password")

        token = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email},
        )

        return user, token
    
    async def request_password_reset(self, email: str) -> None:
        user = await self.repository.get_by_email(email.lower())

        if user is None:
            return

        token = create_password_reset_token(user.email)
        reset_link = f"https://alias-platform.vercel.app/reset-password?token={token}"

        await self.email_service.send_password_reset_email(
            to_email=user.email,
            reset_link=reset_link,
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        email = decode_password_reset_token(token)
        user = await self.repository.get_by_email(email.lower())

        if user is None:
            raise ValidationError("Invalid or expired reset token")

        user.hashed_password = hash_password(new_password)
        await self.repository.db.flush()