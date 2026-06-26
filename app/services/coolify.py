from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class CoolifyApplication:
    id: str
    name: str
    primary_domain: str
    status: str
    repository: str
    environment: str
    updated_at: str
    kind: str = "application"


def _domain_from_fqdn(value: str | None) -> str:
    if not value:
        return "No domain"
    first = value.split(",")[0].strip()
    parsed = urlparse(first if "://" in first else f"https://{first}")
    return parsed.netloc or parsed.path or "No domain"


def normalize_coolify_resource(raw: dict) -> CoolifyApplication:
    return CoolifyApplication(
        id=str(raw.get("uuid") or raw.get("id") or raw.get("name") or "unknown"),
        name=str(raw.get("name") or raw.get("project_name") or raw.get("description") or "Untitled project"),
        primary_domain=_domain_from_fqdn(raw.get("fqdn") or raw.get("domain")),
        status=str(raw.get("status") or raw.get("state") or "unknown"),
        repository=str(raw.get("git_repository") or raw.get("repository") or raw.get("git") or "Manual deploy"),
        environment=str(raw.get("environment_name") or raw.get("environment") or "Production"),
        updated_at=str(raw.get("updated_at") or raw.get("created_at") or ""),
        kind=str(raw.get("type") or raw.get("kind") or "application"),
    )


@dataclass
class CoolifyClient:
    base_url: str
    token: str

    @classmethod
    def from_settings(cls) -> "CoolifyClient":
        s = get_settings()
        return cls(base_url=s.coolify_url.rstrip("/"), token=s.coolify_token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def list_projects(self) -> list[dict]:
        if not self.base_url or not self.token:
            return []
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{self.base_url}/api/v1/projects", headers=self.headers())
            r.raise_for_status()
            return r.json()

    async def list_applications(self) -> list[CoolifyApplication]:
        if not self.base_url or not self.token:
            return self.placeholder_applications()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{self.base_url}/api/v1/applications", headers=self.headers())
            r.raise_for_status()
            payload = r.json()
            items = payload.get("data", payload) if isinstance(payload, dict) else payload
            return [normalize_coolify_resource(item) for item in items]

    def placeholder_applications(self) -> list[CoolifyApplication]:
        return [
            CoolifyApplication("imbaproduction", "Imba Production", "imbaproduction.com", "Migration planned", "Plesk import", "Production", ""),
            CoolifyApplication("montenegro", "Montenegro Experience", "montenegro-experience.me", "Running", "magnetoid/montenegro-experience", "Production", ""),
            CoolifyApplication("dotbooks", "DotBooks", "dotbooks.store", "Running", "magnetoid/dotbooks", "Production", ""),
        ]

    def placeholder_sites(self) -> list[dict[str, str]]:
        return [a.__dict__ for a in self.placeholder_applications()]
