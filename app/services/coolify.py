from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json


class CoolifyApplication(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    primary_domain: str
    status: str
    repository: str
    environment: str
    updated_at: str
    kind: str = "application"
    branch: str = ""
    build_pack: str = ""
    healthcheck_enabled: bool = False


class CoolifyDeployment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    status: str
    created_at: str = ""
    updated_at: str = ""
    commit: str = ""
    branch: str = ""


def _domain_from_fqdn(value: str | None) -> str:
    if not value:
        return "No domain"
    first = value.split(",")[0].strip().strip('"')
    parsed = urlparse(first if "://" in first else f"https://{first}")
    return parsed.netloc or parsed.path or "No domain"


def normalize_coolify_resource(raw: dict[str, Any]) -> CoolifyApplication:
    return CoolifyApplication(
        id=str(raw.get("uuid") or raw.get("id") or raw.get("name") or "unknown"),
        name=str(raw.get("name") or raw.get("project_name") or raw.get("description") or "Untitled project"),
        primary_domain=_domain_from_fqdn(raw.get("fqdn") or raw.get("domain")),
        status=str(raw.get("status") or raw.get("state") or "unknown"),
        repository=str(raw.get("git_repository") or raw.get("repository") or raw.get("git") or "Manual deploy"),
        environment=str(raw.get("environment_name") or raw.get("environment") or "Production"),
        updated_at=str(raw.get("updated_at") or raw.get("created_at") or ""),
        kind=str(raw.get("type") or raw.get("kind") or "application"),
        branch=str(raw.get("git_branch") or ""),
        build_pack=str(raw.get("build_pack") or ""),
        healthcheck_enabled=bool(raw.get("health_check_enabled", False)),
    )


def normalize_coolify_deployment(raw: dict[str, Any]) -> CoolifyDeployment:
    return CoolifyDeployment(
        id=str(raw.get("deployment_uuid") or raw.get("uuid") or raw.get("id") or "unknown"),
        status=str(raw.get("status") or raw.get("state") or "unknown"),
        created_at=str(raw.get("created_at") or ""),
        updated_at=str(raw.get("updated_at") or raw.get("created_at") or ""),
        commit=str(raw.get("commit") or raw.get("commit_sha") or raw.get("git_commit_sha") or ""),
        branch=str(raw.get("branch") or raw.get("git_branch") or ""),
    )


class CoolifyClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(
        cls,
        *,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> "CoolifyClient":
        s = get_settings()
        return cls(
            base_url=s.coolify_url,
            token=s.coolify_token,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def list_projects(self) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/projects",
            headers=self.headers(),
        )
        return payload if isinstance(payload, list) else payload.get("data", [])

    async def list_applications(self, refresh: bool = False) -> list[CoolifyApplication]:
        if not self.is_configured():
            return []

        settings = get_settings()

        async def fetch() -> list[CoolifyApplication]:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="GET",
                url=f"{self.base_url}/api/v1/applications",
                headers=self.headers(),
            )
            items = payload.get("data", payload) if isinstance(payload, dict) else payload
            return [normalize_coolify_resource(item) for item in items]

        if refresh:
            await self.cache.delete("coolify:applications")
        return await self.cache.get_or_set(
            "coolify:applications",
            settings.provider_cache_ttl_seconds,
            fetch,
        )

    async def deploy_application(self, application_uuid: str, force: bool = False) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}

        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/deploy",
            headers=self.headers(),
            params={"uuid": application_uuid, "force": str(force).lower()},
        )
        await self.cache.delete("coolify:applications")
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def start_application(self, application_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/start",
            headers=self.headers(),
        )
        await self.cache.delete("coolify:applications")
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def restart_application(self, application_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/restart",
            headers=self.headers(),
        )
        await self.cache.delete("coolify:applications")
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def stop_application(self, application_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/stop",
            headers=self.headers(),
        )
        await self.cache.delete("coolify:applications")
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def get_application(self, application_uuid: str) -> CoolifyApplication | None:
        if not self.is_configured():
            return None
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}",
            headers=self.headers(),
        )
        if isinstance(payload, dict) and payload.get("uuid"):
            return normalize_coolify_resource(payload)
        return None

    async def get_application_logs(self, application_uuid: str, lines: int = 100) -> str:
        if not self.is_configured():
            return ""
        try:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="GET",
                url=f"{self.base_url}/api/v1/applications/{application_uuid}/logs",
                headers=self.headers(),
                params={"lines": str(lines)},
            )
            if isinstance(payload, list):
                return "\n".join(str(line.get("output", line.get("line", str(line)))) for line in payload)
            if isinstance(payload, dict):
                return payload.get("logs", payload.get("output", str(payload)))
            return str(payload)
        except Exception:
            return "Logs unavailable for this application."

    async def get_application_envs(self, application_uuid: str) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []
        try:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="GET",
                url=f"{self.base_url}/api/v1/applications/{application_uuid}/envs",
                headers=self.headers(),
            )
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                return payload.get("data", [])
            return []
        except Exception:
            return []

    async def cancel_deployment(self, deployment_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/deployments/{deployment_uuid}/cancel",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def list_deployments_for_application(self, application_uuid: str) -> list[CoolifyDeployment]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/deployments/applications/{application_uuid}",
            headers=self.headers(),
        )
        items = payload.get("data", payload) if isinstance(payload, dict) else payload
        results: list[CoolifyDeployment] = []
        for item in items:
            if isinstance(item, str):
                results.append(CoolifyDeployment(id=item, status="unknown"))
            elif isinstance(item, dict):
                results.append(normalize_coolify_deployment(item))
        return results