"""Thin async client for a self-hosted Umami v2 analytics instance.

Self-hosted Umami has no API keys, so we log in with username/password to mint a
bearer token (cached in the shared TTLCache) and re-login once on a 401. All calls
go through the shared retrying ``request_json`` helper and raise ``ProviderAPIError``.

API verified against https://docs.umami.is/docs/api (2026-06): POST /api/auth/login,
GET /api/websites, POST /api/websites, GET /api/websites/{id}/{stats,pageviews,metrics}.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json

_TOKEN_CACHE_KEY = "umami:token"
_TOKEN_TTL_SECONDS = 60 * 60 * 6


class UmamiClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(cls, *, http_client: httpx.AsyncClient, cache: TTLCache) -> "UmamiClient":
        s = get_settings()
        return cls(
            base_url=s.umami_url,
            username=s.umami_username,
            password=s.umami_password,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    # ── Auth ──────────────────────────────────────────────────────────────
    async def _login(self) -> str:
        payload = await request_json(
            self.http_client,
            service="Umami",
            method="POST",
            url=f"{self.base_url}/api/auth/login",
            json_body={"username": self.username, "password": self.password},
        )
        token = payload.get("token") if isinstance(payload, dict) else None
        if not token:
            raise ProviderAPIError(
                service="Umami", message="Login did not return a token.", status_code=502
            )
        await self.cache.set(_TOKEN_CACHE_KEY, str(token), _TOKEN_TTL_SECONDS)
        return str(token)

    async def _token(self, *, refresh: bool = False) -> str:
        if not refresh:
            cached = await self.cache.get(_TOKEN_CACHE_KEY)
            if isinstance(cached, str) and cached:
                return cached
        return await self._login()

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        token = await self._token()
        try:
            return await request_json(
                self.http_client,
                service="Umami",
                method="GET",
                url=f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
        except ProviderAPIError as exc:
            if exc.status_code != 401:
                raise
            token = await self._token(refresh=True)  # expired → re-login once
            return await request_json(
                self.http_client,
                service="Umami",
                method="GET",
                url=f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )

    # ── Websites ──────────────────────────────────────────────────────────
    async def list_websites(self) -> list[dict[str, Any]]:
        payload = await self._get("/api/websites")
        if isinstance(payload, dict):
            data = payload.get("data", payload.get("websites", []))
            return data if isinstance(data, list) else []
        return payload if isinstance(payload, list) else []

    async def create_website(self, name: str, domain: str) -> dict[str, Any]:
        token = await self._token()
        payload = await request_json(
            self.http_client,
            service="Umami",
            method="POST",
            url=f"{self.base_url}/api/websites",
            headers={"Authorization": f"Bearer {token}"},
            json_body={"name": name, "domain": domain},
        )
        return payload if isinstance(payload, dict) else {}

    async def find_or_create_website(self, *, domain: str, name: str) -> dict[str, Any]:
        for site in await self.list_websites():
            if str(site.get("domain", "")).lower() == domain.lower():
                return site
        return await self.create_website(name=name, domain=domain)

    # ── Reports ───────────────────────────────────────────────────────────
    async def get_stats(self, website_id: str, start_ms: int, end_ms: int) -> dict[str, Any]:
        payload = await self._get(
            f"/api/websites/{website_id}/stats",
            params={"startAt": str(start_ms), "endAt": str(end_ms)},
        )
        return payload if isinstance(payload, dict) else {}

    async def get_pageviews(
        self, website_id: str, start_ms: int, end_ms: int, *, unit: str = "day", timezone: str = "UTC"
    ) -> dict[str, Any]:
        payload = await self._get(
            f"/api/websites/{website_id}/pageviews",
            params={
                "startAt": str(start_ms),
                "endAt": str(end_ms),
                "unit": unit,
                "timezone": timezone,
            },
        )
        return payload if isinstance(payload, dict) else {}

    async def get_metrics(
        self, website_id: str, start_ms: int, end_ms: int, metric_type: str, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        payload = await self._get(
            f"/api/websites/{website_id}/metrics",
            params={
                "startAt": str(start_ms),
                "endAt": str(end_ms),
                "type": metric_type,
                "limit": str(limit),
            },
        )
        return payload if isinstance(payload, list) else []

    def tracking_snippet(self, website_id: str) -> str:
        return (
            f'<script async src="{self.base_url}/script.js" '
            f'data-website-id="{website_id}"></script>'
        )
