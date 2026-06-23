from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .refs import ProviderType


class ProviderConnectionState(StrEnum):
    CONNECTED = "connected"
    PARTIALLY_CONNECTED = "partially_connected"
    ACTION_REQUIRED = "action_required"
    FAILED = "failed"


class ProviderDiagnosticCheckCode(StrEnum):
    AUTHENTICATION = "authentication"
    CREDENTIALS_PRESENT = "credentials_present"
    VENUE_ACCESS = "venue_access"
    GROUP_ACCESS = "group_access"
    AVAILABILITY_ACCESS = "availability_access"
    WRITE_ACCESS = "write_access"
    ACCESS_RULES = "access_rules"


class ProviderDiagnosticCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class ProviderDiagnosticCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ProviderDiagnosticCheckCode
    status: ProviderDiagnosticCheckStatus
    message: str
    action_required: str | None = None


class ProviderDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderType
    state: ProviderConnectionState
    checks: list[ProviderDiagnosticCheck]