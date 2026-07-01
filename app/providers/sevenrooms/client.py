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
class SevenRoomsClientConfig:
    client_id: str | None = None
    client_secret: str | None = None
    venue_id: str | None = None
    venue_group_id: str | None = None
    base_url: str = "https://api.sevenrooms.com"


class SevenRoomsClient:
    def __init__(self, config: SevenRoomsClientConfig) -> None:
        self._config = config
        self._http = ProviderHttpClient(base_url=config.base_url)

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def _has_required_config(self) -> bool:
        return bool(
            self._config.client_id
            and self._config.client_secret
            and self._config.venue_id
            and self._config.venue_group_id
        )

    async def authenticate(self) -> str | None:
        """Placeholder for SevenRooms OAuth/client-credentials auth.

        Once official API docs are available, this method will call the
        SevenRooms auth endpoint and return an access token.
        """
        if not self._config.client_id or not self._config.client_secret:
            return None

        return "mock-sevenrooms-token"

    async def build_headers(self) -> dict[str, str]:
        token = await self.authenticate()

        if token is None:
            return {}

        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
    
    async def get_reservation(self, reservation_id: str) -> dict | None:
        """Fetch a SevenRooms reservation by external id.

        Placeholder endpoint until official SevenRooms API documentation
        confirms the exact path and response shape.
        """
        headers = await self.build_headers()

        if not headers:
            return None

        raise NotImplementedError(
            "SevenRooms get reservation endpoint not implemented yet"
        )

    async def health_check(self) -> bool:
        return self._has_required_config()

    async def diagnostics(self) -> ProviderDiagnostics:
        checks: list[ProviderDiagnosticCheck] = []

        if self._config.client_id and self._config.client_secret:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.CREDENTIALS_PRESENT,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="SevenRooms Client ID and Client Secret configured",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.CREDENTIALS_PRESENT,
                    status=ProviderDiagnosticCheckStatus.FAILED,
                    message="SevenRooms Client ID or Client Secret missing",
                    action_required="Provide SevenRooms Client ID and Client Secret",
                )
            )

        if self._config.venue_id:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.VENUE_ACCESS,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="SevenRooms Venue ID configured",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.VENUE_ACCESS,
                    status=ProviderDiagnosticCheckStatus.WARNING,
                    message="SevenRooms Venue ID not configured",
                    action_required="Provide the SevenRooms Venue ID",
                )
            )

        if self._config.venue_group_id:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.GROUP_ACCESS,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="SevenRooms Venue Group ID configured",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.GROUP_ACCESS,
                    status=ProviderDiagnosticCheckStatus.WARNING,
                    message="SevenRooms Venue Group ID not configured",
                    action_required="Provide the SevenRooms Venue Group ID / Group ID",
                )
            )

        state = (
            ProviderConnectionState.CONNECTED
            if await self.health_check()
            else ProviderConnectionState.ACTION_REQUIRED
        )

        return ProviderDiagnostics(
            provider=ProviderType.SEVENROOMS,
            state=state,
            checks=checks,
        )
    
    async def get_availability(self, payload: dict) -> dict:
        """Fetch SevenRooms availability.

        Placeholder until official SevenRooms API documentation confirms
        endpoint, query params, and response shape.
        """
        headers = await self.build_headers()

        if not headers:
            return {"slots": []}

        raise NotImplementedError(
            "SevenRooms availability endpoint not implemented yet"
        )
    
    async def create_reservation(self, payload: dict) -> dict:
        """Create a SevenRooms reservation.

        Placeholder until official SevenRooms API documentation confirms
        endpoint, request body, and response shape.
        """
        headers = await self.build_headers()

        if not headers:
            raise NotImplementedError(
                "SevenRooms create reservation requires authentication"
            )

        raise NotImplementedError(
            "SevenRooms create reservation endpoint not implemented yet"
        )
    
    async def update_reservation(
        self,
        reservation_id: str,
        payload: dict,
    ) -> dict:
        """Update a SevenRooms reservation.

        Placeholder until official SevenRooms API documentation confirms
        endpoint, request body, and response shape.
        """
        headers = await self.build_headers()

        if not headers:
            raise NotImplementedError(
                "SevenRooms update reservation requires authentication"
            )

        raise NotImplementedError(
            "SevenRooms update reservation endpoint not implemented yet"
        )