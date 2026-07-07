"""OpenRouter client — AI-model reselling via the Provisioning (Management) API.

A single platform **management key** mints per-tenant **runtime keys** with spend caps
(`POST /api/v1/keys`); the tenant calls OpenRouter directly with their key, which
OpenRouter meters + auto-disables at the cap. The create response returns the secret key
**once** — we surface it and never store it (only the non-secret ``hash`` for management).
All calls go through the shared retrying ``request_json`` helper.
"""

from typing import Any

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json

OPENROUTER_API = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    def __init__(
        self, *, provisioning_key: str, http_client: httpx.AsyncClient, cache: TTLCache
    ) -> None:
        self.provisioning_key = provisioning_key
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(cls, *, http_client: httpx.AsyncClient, cache: TTLCache) -> "OpenRouterClient":
        return cls(
            provisioning_key=get_settings().openrouter_provisioning_key,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.provisioning_key)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.provisioning_key}", "Content-Type": "application/json"}

    async def list_models(self, refresh: bool = False) -> list[dict[str, Any]]:
        """GET /models — the public model catalog (the resellable menu)."""
        async def fetch() -> list[dict[str, Any]]:
            payload = await request_json(
                self.http_client, service="OpenRouter", method="GET", url=f"{OPENROUTER_API}/models",
            )
            data = payload.get("data") if isinstance(payload, dict) else None
            return data if isinstance(data, list) else []

        if refresh:
            await self.cache.delete("openrouter:models")
        return await self.cache.get_or_set(
            "openrouter:models", get_settings().provider_cache_ttl_seconds, fetch
        )

    async def create_key(
        self, name: str, *, limit: float | None = None, limit_reset: str | None = None
    ) -> dict[str, Any]:
        """POST /keys — mint a runtime key. Returns {key: <secret, once>, data: {hash,...}}."""
        body: dict[str, Any] = {"name": name}
        if limit is not None:
            body["limit"] = limit
        if limit_reset:
            body["limitReset"] = limit_reset
        payload = await request_json(
            self.http_client, service="OpenRouter", method="POST",
            url=f"{OPENROUTER_API}/keys", headers=self.headers(), json_body=body,
        )
        return payload if isinstance(payload, dict) else {}

    async def list_keys(self, offset: int = 0) -> list[dict[str, Any]]:
        payload = await request_json(
            self.http_client, service="OpenRouter", method="GET",
            url=f"{OPENROUTER_API}/keys", headers=self.headers(), params={"offset": offset},
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        return data if isinstance(data, list) else []

    async def get_key(self, key_hash: str) -> dict[str, Any]:
        payload = await request_json(
            self.http_client, service="OpenRouter", method="GET",
            url=f"{OPENROUTER_API}/keys/{key_hash}", headers=self.headers(),
        )
        return payload.get("data", {}) if isinstance(payload, dict) else {}

    async def update_key(
        self, key_hash: str, *, limit: float | None = None, disabled: bool | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if limit is not None:
            body["limit"] = limit
        if disabled is not None:
            body["disabled"] = disabled
        payload = await request_json(
            self.http_client, service="OpenRouter", method="PATCH",
            url=f"{OPENROUTER_API}/keys/{key_hash}", headers=self.headers(), json_body=body,
        )
        return payload.get("data", {}) if isinstance(payload, dict) else {}

    async def delete_key(self, key_hash: str) -> None:
        await request_json(
            self.http_client, service="OpenRouter", method="DELETE",
            url=f"{OPENROUTER_API}/keys/{key_hash}", headers=self.headers(),
        )


__all__ = ["OPENROUTER_API", "OpenRouterClient", "ProviderAPIError"]
