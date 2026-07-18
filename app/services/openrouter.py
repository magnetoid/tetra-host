"""OpenRouter client — AI-model reselling via the Provisioning (Management) API.

A single platform **management key** mints per-tenant **runtime keys** with spend caps
(`POST /api/v1/keys`); the tenant calls OpenRouter directly with their key, which
OpenRouter meters + auto-disables at the cap. The create response returns the secret key
**once** — we surface it and never store it (only the non-secret ``hash`` for management).
All calls go through the shared retrying ``request_json`` helper.
"""

import logging
from typing import Any

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json

logger = logging.getLogger(__name__)

OPENROUTER_API = "https://openrouter.ai/api/v1"


# How the platform bills AI, decided by which credential is configured:
#   "keys"    — Model B: a PROVISIONING key mints a per-tenant OpenRouter runtime key with
#               an OpenRouter-enforced hard cap (each tenant calls OpenRouter directly).
#   "gateway" — Model A: a single shared RUNTIME key; tenants call Tetra's /ai/chat, Tetra
#               proxies to OpenRouter, reads the inline per-request cost, and meters each
#               tenant into its own credit wallet + ledger (prepaid, soft caps).
#   "disabled"— neither key set.
MODE_KEYS = "keys"
MODE_GATEWAY = "gateway"
MODE_DISABLED = "disabled"

# LLM completions can run well past the 20s provider default; give the gateway room.
CHAT_TIMEOUT_SECONDS = 120.0


class OpenRouterClient:
    def __init__(
        self,
        *,
        provisioning_key: str = "",
        runtime_key: str = "",
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.provisioning_key = provisioning_key
        self.runtime_key = runtime_key
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(cls, *, http_client: httpx.AsyncClient, cache: TTLCache) -> "OpenRouterClient":
        settings = get_settings()
        return cls(
            provisioning_key=settings.openrouter_provisioning_key,
            runtime_key=settings.openrouter_runtime_key,
            http_client=http_client,
            cache=cache,
        )

    def mode(self) -> str:
        """Provisioning key wins (hard caps); else a runtime key powers the gateway."""
        if self.provisioning_key:
            return MODE_KEYS
        if self.runtime_key:
            return MODE_GATEWAY
        return MODE_DISABLED

    def is_configured(self) -> bool:
        return self.mode() != MODE_DISABLED

    def headers(self) -> dict[str, str]:
        """Management/provisioning headers (key-minting — Model B)."""
        return {"Authorization": f"Bearer {self.provisioning_key}", "Content-Type": "application/json"}

    def runtime_headers(self) -> dict[str, str]:
        """Runtime headers for inference + balance (the shared gateway key — Model A)."""
        return {"Authorization": f"Bearer {self.runtime_key}", "Content-Type": "application/json"}

    async def get_credits(self) -> dict[str, Any]:
        """GET /credits — the shared key's balance basis (total_credits − total_usage)."""
        payload = await request_json(
            self.http_client, service="OpenRouter", method="GET",
            url=f"{OPENROUTER_API}/credits", headers=self.runtime_headers(),
        )
        return payload.get("data", {}) if isinstance(payload, dict) else {}

    async def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /chat/completions through the shared runtime key (gateway pass-through).

        OpenRouter returns ``usage.cost`` (USD it charged us) inline on every response —
        that's the metering basis. Single attempt (no retry) so a mid-flight failure can't
        double-execute + double-bill; a long timeout covers slow completions.
        """
        payload = await request_json(
            self.http_client, service="OpenRouter", method="POST",
            url=f"{OPENROUTER_API}/chat/completions", headers=self.runtime_headers(),
            json_body=body, max_attempts=1, timeout=CHAT_TIMEOUT_SECONDS,
        )
        return payload if isinstance(payload, dict) else {}

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
        logger.info("minting OpenRouter runtime key '%s' (limit=%s)", name, limit)
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
        logger.info("updating OpenRouter key %s (limit=%s, disabled=%s)", key_hash, limit, disabled)
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
        logger.info("deleting OpenRouter key %s", key_hash)
        await request_json(
            self.http_client, service="OpenRouter", method="DELETE",
            url=f"{OPENROUTER_API}/keys/{key_hash}", headers=self.headers(),
        )


__all__ = [
    "MODE_DISABLED",
    "MODE_GATEWAY",
    "MODE_KEYS",
    "OPENROUTER_API",
    "OpenRouterClient",
    "ProviderAPIError",
]
