from dataclasses import dataclass
from urllib.parse import urlparse
import json
import subprocess

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


@dataclass(frozen=True)
class CoolifyActionResult:
    ok: bool
    action: str
    application_id: str
    detail: str
    source: str


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


def _extract_resource_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "applications", "resources", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if any(k in payload for k in ("uuid", "id", "name", "project_name")):
            return [payload]
    return []


@dataclass
class CoolifyClient:
    base_url: str
    token: str
    action_helper: str = ""

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    @classmethod
    def from_settings(cls) -> "CoolifyClient":
        s = get_settings()
        return cls(
            base_url=s.coolify_url.rstrip("/"),
            token=s.coolify_token,
            action_helper=s.coolify_action_helper,
        )

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def list_projects(self) -> list[dict]:
        if not self.is_configured():
            return []
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{self.base_url}/api/v1/projects", headers=self.headers())
            r.raise_for_status()
            return r.json()

    async def list_applications(self) -> list[CoolifyApplication]:
        if not self.is_configured():
            return self.placeholder_applications()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(f"{self.base_url}/api/v1/applications", headers=self.headers())
                r.raise_for_status()
                payload = r.json()
        except (httpx.HTTPError, ValueError):
            return self.placeholder_applications()

        items = _extract_resource_items(payload)
        if not items:
            return self.placeholder_applications()

        return [normalize_coolify_resource(item) for item in items]

    async def trigger_action(self, application_id: str, action: str) -> CoolifyActionResult:
        if action not in {"deploy", "restart"}:
            return CoolifyActionResult(False, action, application_id, "Unsupported action", "app")
        if self.action_helper:
            helper_result = self._trigger_action_with_helper(application_id, action)
            if helper_result is not None:
                return helper_result
        if not self.is_configured():
            return CoolifyActionResult(False, action, application_id, "Coolify is not configured", "app")
        endpoint = f"{self.base_url}/api/v1/applications/{application_id}/{action}"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(endpoint, headers=self.headers())
                response.raise_for_status()
                payload = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            return CoolifyActionResult(False, action, application_id, str(exc), "app")

        detail = "Action accepted"
        if isinstance(payload, dict):
            detail = str(payload.get("message") or payload.get("status") or detail)
        return CoolifyActionResult(True, action, application_id, detail, "app")

    def _trigger_action_with_helper(self, application_id: str, action: str) -> CoolifyActionResult | None:
        try:
            completed = subprocess.run(
                [self.action_helper, self.base_url, self.token, application_id, action],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except OSError:
            return None
        except subprocess.TimeoutExpired:
            return CoolifyActionResult(False, action, application_id, "Go helper timed out", "go-helper")

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "Go helper failed"
            return CoolifyActionResult(False, action, application_id, detail, "go-helper")

        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            return CoolifyActionResult(False, action, application_id, "Invalid Go helper output", "go-helper")

        return CoolifyActionResult(
            ok=bool(payload.get("ok")),
            action=str(payload.get("action") or action),
            application_id=str(payload.get("application_id") or application_id),
            detail=str(payload.get("detail") or "Action executed"),
            source="go-helper",
        )

    def placeholder_applications(self) -> list[CoolifyApplication]:
        return [
            CoolifyApplication("imbaproduction", "Imba Production", "imbaproduction.com", "Migration planned", "Plesk import", "Production", ""),
            CoolifyApplication("montenegro", "Montenegro Experience", "montenegro-experience.me", "Running", "magnetoid/montenegro-experience", "Production", ""),
            CoolifyApplication("dotbooks", "DotBooks", "dotbooks.store", "Running", "magnetoid/dotbooks", "Production", ""),
        ]

    def placeholder_sites(self) -> list[dict[str, str]]:
        return [a.__dict__ for a in self.placeholder_applications()]
