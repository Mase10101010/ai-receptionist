from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse, 
    UserCreate, 
    UserLogin, 
    UserResponse,
)
from app.services.auth_service import AuthService
from app.api.dependencies import CurrentUserDep
from app.services.email_service import EmailService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    repository = UserRepository(db)
    email_service = EmailService()

    return AuthService(
        repository,
        email_service,
    )


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

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.request_password_reset(str(payload.email))

    return MessageResponse(
        message="If an account exists for this email, a reset link has been sent.",
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.reset_password(
        token=payload.token,
        new_password=payload.new_password,
    )

    await service.repository.db.commit()

    return MessageResponse(
        message="Password reset successfully.",
    )

@router.get(
    "/verify-email",
    response_model=MessageResponse,
)
async def verify_email(
    token: str = Query(...),
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.verify_email(token)
    await service.repository.db.commit()

    return MessageResponse(
        message="Email verified successfully.",
    )

@router.post(
    "/send-verification-email",
    response_model=MessageResponse,
)
async def send_verification_email(
    current_user: CurrentUserDep,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.send_verification_email(current_user)

    return MessageResponse(
        message="Verification email sent.",
    )

@router.get("/me", response_model=UserResponse)
async def me(
    current_user: CurrentUserDep,
) -> UserResponse:
    return UserResponse.model_validate(current_user)