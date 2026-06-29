import json
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


class CredentialCryptoError(RuntimeError):
    pass


class CredentialEncryptionService:
    def __init__(self, key: str) -> None:
        if not key:
            raise CredentialCryptoError("Provider credentials encryption key is missing")

        self._fernet = Fernet(key.encode("utf-8"))

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")
    
    @classmethod
    def from_settings(cls) -> "CredentialEncryptionService":
        if not settings.PROVIDER_CREDENTIALS_KEY:
            raise CredentialCryptoError(
                "PROVIDER_CREDENTIALS_KEY is not configured"
            )
        return cls(settings.PROVIDER_CREDENTIALS_KEY)

    async def encrypt(
        self,
        credentials: Mapping[str, Any],
    ) -> dict[str, str]:
        payload = json.dumps(
            dict(credentials),
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        token = self._fernet.encrypt(payload).decode("utf-8")

        return {
            "v": "1",
            "alg": "fernet",
            "token": token,
        }

    async def decrypt(
        self,
        encrypted: Mapping[str, str],
    ) -> dict[str, Any]:
        try:
            token = encrypted["token"].encode("utf-8")
            payload = self._fernet.decrypt(token)
            return json.loads(payload.decode("utf-8"))
        except (KeyError, InvalidToken, json.JSONDecodeError) as exc:
            raise CredentialCryptoError("Invalid encrypted provider credentials") from exc