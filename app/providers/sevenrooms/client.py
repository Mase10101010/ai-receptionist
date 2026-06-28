from dataclasses import dataclass

from app.providers.contract.diagnostics import (
    ProviderConnectionState,
    ProviderDiagnosticCheck,
    ProviderDiagnosticCheckCode,
    ProviderDiagnosticCheckStatus,
    ProviderDiagnostics,
)
from app.providers.contract.refs import ProviderType


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

    @property
    def base_url(self) -> str:
        return self._config.base_url

    async def health_check(self) -> bool:
        return (
            self._config.client_id is not None
            and self._config.client_secret is not None
            and self._config.venue_id is not None
            and self._config.venue_group_id is not None
        )

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