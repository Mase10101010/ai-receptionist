from dataclasses import dataclass

from app.providers.contract.diagnostics import (
    ProviderConnectionState,
    ProviderDiagnosticCheck,
    ProviderDiagnosticCheckCode,
    ProviderDiagnosticCheckStatus,
    ProviderDiagnostics,
)
from app.providers.contract.refs import ProviderType
from app.providers.http.client import ProviderHttpClient


@dataclass(frozen=True, slots=True)
class TheForkClientConfig:
    client_id: str | None = None
    client_secret: str | None = None
    restaurant_id: str | None = None
    base_url: str = "https://api.thefork.com"
    token_url: str | None = None
    scopes: tuple[str, ...] = ()


class TheForkClient:
    def __init__(self, config: TheForkClientConfig) -> None:
        self._config = config
        self._http = ProviderHttpClient(base_url=config.base_url)

    def _has_required_config(self) -> bool:
        return bool(
            self._config.client_id
            and self._config.client_secret
            and self._config.restaurant_id
        )

    async def authenticate(self) -> str | None:
        if not self._config.client_id or not self._config.client_secret:
            return None

        if not self._config.token_url:
            return "mock-thefork-token"

        payload = {
            "grant_type": "client_credentials",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
        }

        if self._config.scopes:
            payload["scope"] = " ".join(self._config.scopes)

        response = await self._http.post(
            self._config.token_url,
            json=payload,
        )

        token = response.get("access_token")

        if not isinstance(token, str) or not token:
            return None

        return token

    async def build_headers(self) -> dict[str, str]:
        token = await self.authenticate()

        if token is None:
            return {}

        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def health_check(self) -> bool:
        return self._has_required_config()

    async def diagnostics(self) -> ProviderDiagnostics:
        checks: list[ProviderDiagnosticCheck] = []

        if self._config.client_id and self._config.client_secret:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.CREDENTIALS_PRESENT,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="TheFork Client ID and Client Secret configured",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.CREDENTIALS_PRESENT,
                    status=ProviderDiagnosticCheckStatus.FAILED,
                    message="TheFork Client ID or Client Secret missing",
                    action_required="Provide TheFork Client ID and Client Secret",
                )
            )

        if self._config.restaurant_id:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.VENUE_ACCESS,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="TheFork restaurant ID configured",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.VENUE_ACCESS,
                    status=ProviderDiagnosticCheckStatus.WARNING,
                    message="TheFork restaurant ID not configured",
                    action_required="Provide TheFork restaurant ID",
                )
            )

        state = (
            ProviderConnectionState.CONNECTED
            if await self.health_check()
            else ProviderConnectionState.ACTION_REQUIRED
        )

        return ProviderDiagnostics(
            provider=ProviderType.THEFORK,
            state=state,
            checks=checks,
        )
    
    async def get_availability(self, payload: dict) -> dict:
        """Fetch TheFork availability.

        Placeholder until final TheFork API wiring is implemented.
        """
        headers = await self.build_headers()

        if not headers:
            return {"slots": []}

        raise NotImplementedError(
            "TheFork availability endpoint not implemented yet"
        )
    
    async def create_reservation(self, payload: dict) -> dict:
        """Create a reservation in TheFork.

        Placeholder until final API integration.
        """
        headers = await self.build_headers()

        if not headers:
            return {}

        raise NotImplementedError(
            "TheFork create reservation endpoint not implemented yet"
        )
    
    async def update_reservation(
        self,
        reservation_id: str,
        payload: dict,
    ) -> dict:
        """Update a TheFork reservation.

        Placeholder until final API integration.
        """
        headers = await self.build_headers()

        if not headers:
            return {}

        raise NotImplementedError(
            "TheFork update reservation endpoint not implemented yet"
        )

    async def cancel_reservation(
        self,
        reservation_id: str,
        payload: dict,
    ) -> dict:
        """Cancel a TheFork reservation.

        Placeholder until final API integration.
        """
        headers = await self.build_headers()

        if not headers:
            return {}

        raise NotImplementedError(
            "TheFork cancel reservation endpoint not implemented yet"
        )
    
    async def get_reservation(
        self,
        reservation_id: str,
    ) -> dict | None:
        """Retrieve a reservation from TheFork.

        Placeholder until final API integration.
        """
        headers = await self.build_headers()

        if not headers:
            return None

        raise NotImplementedError(
            "TheFork get reservation endpoint not implemented yet"
        )