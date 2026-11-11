"""Read-only Coolify API client — the importer's only view of a Coolify app.

Tetra Host no longer manages apps through Coolify; Coolify is an import source. The importer
reads an application's metadata (name, fqdn, status, auto-deploy) here, and its compose, .env
and volumes from the Coolify data directory on the host (``host.py``).
"""

from typing import Any

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json


class CoolifyClient:
    def __init__(
        self, *, base_url: str, token: str, http_client: httpx.AsyncClient, cache: TTLCache
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(cls, *, http_client: httpx.AsyncClient, cache: TTLCache) -> "CoolifyClient":
        s = get_settings()
        return cls(base_url=s.coolify_url, token=s.coolify_token, http_client=http_client, cache=cache)

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def get_application_raw(self, application_uuid: str) -> dict[str, Any]:
        """The raw Coolify application record, or ``{}`` when Coolify is not configured."""
        if not self.is_configured():
            return {}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {}
