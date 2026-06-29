from collections.abc import Mapping
from typing import Any

import httpx

from app.providers.http.errors import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

class ProviderHttpClient:
    def __init__(
            self,
            *,
            base_url: str,
            timeout_seconds: float = 10.0,
            default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)
        self._default_headers = dict(default_headers or {})

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_headers = {
            **self._default_headers,
            **dict(headers or {}),
        }
        
        url = f"{self._base_url}/{path.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    params=params,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderHttpError("Provider HTTP request failed") from exc
        
        if response.status_code == 401:
            raise ProviderAuthenticationError("Provider authentication failed ")
        
        if response.status_code == 403:
            raise ProviderAuthorizationError("Provider authorization failed")
        
        if response.status_code == 429:
            raise ProviderRateLimitError("Provider rate limit exceeded")
        
        if response.status_code >= 500:
            raise ProviderUnavailableError("Provider is temporarily unavailable")
        
        if response.status_code >= 400:
            raise ProviderHttpError(
                f"Provider request failed with status {response.status_code}"
            )
        
        if not response.content:
            return {}
        
        data = response.json()

        if not isinstance(data, dict):
            return {"data": data}
        
        return data 
    
    async def get(self, path: str, **kwargs):
        return await self.request("GET", path, **kwargs)
    
    async def post(self, path: str, **kwargs):
        return await self.request("POST", path, **kwargs)
    
    async def put(self, path: str, **kwargs):
        return await self.request("PUT", path, **kwargs)
    
    async def delete(self, path: str, **kwargs):
        return await self.request("DELETE", path **kwargs)