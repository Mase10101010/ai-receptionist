from app.core.exceptions import ConflictError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserCreate, UserLogin


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

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