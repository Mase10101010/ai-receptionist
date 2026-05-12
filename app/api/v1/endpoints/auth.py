from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService
from app.api.dependencies import CurrentUserDep

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    repository = UserRepository(db)
    return AuthService(repository)


@router.post("/register", response_model=TokenResponse)
async def register(
    payload: UserCreate,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user, token = await service.register(payload)
    await service.repository.db.commit()

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user, token = await service.login(payload)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )

@router.get("/me", response_model=UserResponse)
async def me(
    current_user: CurrentUserDep,
) -> UserResponse:
    return UserResponse.model_validate(current_user)