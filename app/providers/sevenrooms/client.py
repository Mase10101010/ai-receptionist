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
    api_key: str | None = None
    venue_id: str | None = None
    base_url: str = "https://api.sevenrooms.com"


class SevenRoomsClient:
    def __init__(self, config: SevenRoomsClientConfig) -> None:
        self._config = config

    @property
    def base_url(self) -> str:
        return self._config.base_url

    async def health_check(self) -> bool:
        return self._config.api_key is not None

    async def diagnostics(self) -> ProviderDiagnostics:
        checks: list[ProviderDiagnosticCheck] = []

        if self._config.api_key:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.CREDENTIALS_PRESENT,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="API credentials present",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.CREDENTIALS_PRESENT,
                    status=ProviderDiagnosticCheckStatus.FAILED,
                    message="API credentials missing",
                    action_required="Provide SevenRooms credentials",
                )
            )

        if self._config.venue_id:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.VENUE_ACCESS,
                    status=ProviderDiagnosticCheckStatus.PASSED,
                    message="Venue ID configured",
                )
            )
        else:
            checks.append(
                ProviderDiagnosticCheck(
                    code=ProviderDiagnosticCheckCode.VENUE_ACCESS,
                    status=ProviderDiagnosticCheckStatus.WARNING,
                    message="Venue ID not configured",
                    action_required="Provide a SevenRooms venue ID",
                )
            )

        state = (
            ProviderConnectionState.CONNECTED
            if self._config.api_key
            else ProviderConnectionState.ACTION_REQUIRED
        )

        return ProviderDiagnostics(
            provider=ProviderType.SEVENROOMS,
            state=state,
            checks=checks,
        )