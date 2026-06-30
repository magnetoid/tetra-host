"""Thin async client for a self-hosted GlitchTip (Sentry-API-compatible) instance.

Auth is a bearer auth-token created in GlitchTip. Endpoints follow the Sentry v0 API:
list org projects, list teams, create a project under a team, fetch a project's client
keys (DSN), and list a project's issues. All calls go through the shared retrying
``request_json`` helper and raise ``ProviderAPIError``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json


class GlitchtipClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        org: str,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.org = org
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(cls, *, http_client: httpx.AsyncClient, cache: TTLCache) -> "GlitchtipClient":
        s = get_settings()
        return cls(
            base_url=s.glitchtip_url,
            token=s.glitchtip_token,
            org=s.glitchtip_org,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token and self.org)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        return await request_json(
            self.http_client,
            service="GlitchTip",
            method="GET",
            url=f"{self.base_url}{path}",
            headers=self.headers(),
            params=params,
        )

    # ── Projects / teams ──────────────────────────────────────────────────
    async def list_projects(self) -> list[dict[str, Any]]:
        payload = await self._get(f"/api/0/organizations/{self.org}/projects/")
        return payload if isinstance(payload, list) else []

    async def list_teams(self) -> list[dict[str, Any]]:
        payload = await self._get(f"/api/0/organizations/{self.org}/teams/")
        return payload if isinstance(payload, list) else []

    async def create_project(self, *, name: str, team_slug: str) -> dict[str, Any]:
        payload = await request_json(
            self.http_client,
            service="GlitchTip",
            method="POST",
            url=f"{self.base_url}/api/0/teams/{self.org}/{team_slug}/projects/",
            headers=self.headers(),
            json_body={"name": name, "platform": "javascript"},
        )
        return payload if isinstance(payload, dict) else {}

    async def find_or_create_project(self, *, slug: str, name: str) -> dict[str, Any] | None:
        for project in await self.list_projects():
            if str(project.get("slug", "")).lower() == slug.lower():
                return project
        teams = await self.list_teams()
        if not teams:
            return None  # nowhere to create it; caller surfaces a "not ready" reason
        team_slug = str(teams[0].get("slug") or "")
        if not team_slug:
            return None
        return await self.create_project(name=name, team_slug=team_slug)

    async def get_project_dsn(self, project_slug: str) -> str:
        payload = await self._get(f"/api/0/projects/{self.org}/{project_slug}/keys/")
        keys = payload if isinstance(payload, list) else []
        for key in keys:
            dsn = key.get("dsn") if isinstance(key, dict) else None
            if isinstance(dsn, dict) and dsn.get("public"):
                return str(dsn["public"])
        return ""

    # ── Issues ────────────────────────────────────────────────────────────
    async def list_issues(
        self, project_slug: str, *, query: str = "is:unresolved", limit: int = 25
    ) -> list[dict[str, Any]]:
        payload = await self._get(
            f"/api/0/projects/{self.org}/{project_slug}/issues/",
            params={"query": query, "limit": str(limit)},
        )
        return payload if isinstance(payload, list) else []
