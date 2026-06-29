from collections.abc import Mapping
from typing import Any

from app.providers.credential_crypto import CredentialEncryptionService


class FernetCredentialDecryptor:
    def __init__(self) -> None:
        self._crypto = CredentialEncryptionService.from_settings()

    async def decrypt(
        self,
        encrypted: Mapping[str, str],
    ) -> Mapping[str, Any]:
        return await self._crypto.decrypt(encrypted)