from dataclasses import dataclass


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