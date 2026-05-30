from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
def create_password_reset_token(email: str) -> str:
    return create_access_token(
        subject=email,
        expires_delta=timedelta(minutes=30),
        extra_claims={"type": "password_reset"},
    )


def decode_password_reset_token(token: str) -> str:
    payload = decode_access_token(token)

    if payload.get("type") != "password_reset":
        raise ValueError("Invalid reset token")

    email = payload.get("sub")

    if not email:
        raise ValueError("Invalid reset token")

    return str(email)

def create_email_verification_token(email: str) -> str:
    return create_access_token(
        subject=email,
        expires_delta=timedelta(hours=24),
        extra_claims={"type": "email_verification"},
    )


def decode_email_verification_token(token: str) -> str:
    payload = decode_access_token(token)

    if payload.get("type") != "email_verification":
        raise ValueError("Invalid email verification token")

    email = payload.get("sub")

    if not email:
        raise ValueError("Invalid email verification token")

    return str(email)