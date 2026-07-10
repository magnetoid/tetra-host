import json
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json

# Coolify v4 supported database types — validated before interpolating into URL path.
# Source: POST /api/v1/databases/{type} endpoints confirmed in openapi.json.
DB_TYPE_ALLOWLIST: frozenset[str] = frozenset({
    "postgresql", "mysql", "mariadb", "mongodb",
    "redis", "keydb", "dragonfly", "clickhouse",
})


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
    # Coolify project grouping: applications sharing a project belong to one
    # Tetra project (tenant > project > deployment). environment_id links an app
    # to its Coolify environment, which resolves to project_uuid/project_name.
    environment_id: int = 0
    project_uuid: str = ""
    project_name: str = ""
    # Extended fields from full API response
    description: str = ""
    fqdn: str = ""
    install_command: str = ""
    build_command: str = ""
    start_command: str = ""
    base_directory: str = ""
    publish_directory: str = ""
    ports_exposes: str = ""
    ports_mappings: str = ""
    health_check_path: str = ""
    health_check_port: str = ""
    health_check_interval: int = 0
    health_check_timeout: int = 0
    health_check_retries: int = 0
    limits_memory: str = ""
    limits_cpu: str = ""
    redirect: str = ""
    docker_registry_image_name: str = ""
    docker_registry_image_tag: str = ""
    static_image: str = ""
    instant_deploy: bool = False


class CoolifyDeployment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    status: str
    created_at: str = ""
    updated_at: str = ""
    commit: str = ""
    branch: str = ""
    deployment_log: str = ""


class CoolifyScheduledTask(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str = ""
    command: str = ""
    frequency: str = ""
    status: str = ""
    raw: dict[str, Any] = {}


class CoolifyStorage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str = ""
    mount_path: str = ""
    host_path: str = ""
    content: str = ""
    raw: dict[str, Any] = {}


class CoolifyDatabase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    type: str = ""
    status: str = "unknown"
    internal_db_url: str = ""
    public_port: str = ""
    image: str = ""
    created_at: str = ""
    description: str = ""
    limits_memory: str = ""
    limits_cpu: str = ""


class CoolifyService(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    type: str = ""
    status: str = "unknown"
    description: str = ""
    created_at: str = ""
    fqdn: str = ""


class CoolifyServer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    ip: str = ""
    user: str = ""
    description: str = ""
    is_reachable: bool = False
    is_usable: bool = False


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
        environment_id=int(raw.get("environment_id") or 0),
        branch=str(raw.get("git_branch") or ""),
        build_pack=str(raw.get("build_pack") or ""),
        healthcheck_enabled=bool(raw.get("health_check_enabled", False)),
        description=str(raw.get("description") or ""),
        fqdn=str(raw.get("fqdn") or ""),
        install_command=str(raw.get("install_command") or ""),
        build_command=str(raw.get("build_command") or ""),
        start_command=str(raw.get("start_command") or ""),
        base_directory=str(raw.get("base_directory") or ""),
        publish_directory=str(raw.get("publish_directory") or ""),
        ports_exposes=str(raw.get("ports_exposes") or ""),
        ports_mappings=str(raw.get("ports_mappings") or ""),
        health_check_path=str(raw.get("health_check_path") or ""),
        health_check_port=str(raw.get("health_check_port") or ""),
        health_check_interval=int(raw.get("health_check_interval") or 0),
        health_check_timeout=int(raw.get("health_check_timeout") or 0),
        health_check_retries=int(raw.get("health_check_retries") or 0),
        limits_memory=str(raw.get("limits_memory") or ""),
        limits_cpu=str(raw.get("limits_cpu") or ""),
        redirect=str(raw.get("redirect") or ""),
        docker_registry_image_name=str(raw.get("docker_registry_image_name") or ""),
        docker_registry_image_tag=str(raw.get("docker_registry_image_tag") or ""),
        static_image=str(raw.get("static_image") or ""),
        instant_deploy=bool(raw.get("instant_deploy", False)),
    )


def normalize_coolify_deployment(raw: dict[str, Any]) -> CoolifyDeployment:
    return CoolifyDeployment(
        id=str(raw.get("deployment_uuid") or raw.get("uuid") or raw.get("id") or "unknown"),
        status=str(raw.get("status") or raw.get("state") or "unknown"),
        created_at=str(raw.get("created_at") or ""),
        updated_at=str(raw.get("updated_at") or raw.get("created_at") or ""),
        commit=str(raw.get("commit") or raw.get("commit_sha") or raw.get("git_commit_sha") or ""),
        branch=str(raw.get("branch") or raw.get("git_branch") or ""),
        # Coolify returns the build log under "logs" (a JSON-array string) on both the
        # list and single-deployment endpoints; "deployment_log" is a defensive fallback.
        deployment_log=str(raw.get("logs") or raw.get("deployment_log") or ""),
    )


def parse_deployment_log_lines(raw: str | None) -> list[dict[str, str]]:
    """Normalize a Coolify ``deployment_log`` into structured lines.

    Coolify stores the build log either as a JSON array of objects
    (``{"output", "type", "timestamp"}``), a JSON object wrapping such an
    array, or a plain newline-delimited string. This returns a uniform list of
    ``{"output", "type", "timestamp"}`` dicts so the UI can render each line
    consistently and a stream can diff by line count.
    """
    if not raw:
        return []

    text_value = raw if isinstance(raw, str) else str(raw)

    parsed: Any
    try:
        parsed = json.loads(text_value)
    except (ValueError, TypeError):
        parsed = None

    if isinstance(parsed, list):
        items: list[Any] = parsed
    elif isinstance(parsed, dict):
        nested = parsed.get("logs") or parsed.get("data") or parsed.get("output")
        items = nested if isinstance(nested, list) else [parsed]
    else:
        return [
            {"output": line, "type": "stdout", "timestamp": ""}
            for line in text_value.splitlines()
            if line.strip()
        ]

    lines: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            output = item.get("output", item.get("line", item.get("message", "")))
            lines.append(
                {
                    "output": str(output),
                    "type": str(item.get("type", "stdout")),
                    "timestamp": str(item.get("timestamp", item.get("created_at", ""))),
                }
            )
        else:
            lines.append({"output": str(item), "type": "stdout", "timestamp": ""})
    return lines


def _extract_deployment_uuid(result: dict[str, Any]) -> str:
    """Pull the queued deployment uuid out of a Coolify deploy response.

    Coolify returns either ``{"deployments": [{"deployment_uuid": ...}]}`` or a
    flat ``{"deployment_uuid": ...}`` depending on version; tolerate both.
    """
    deployments = result.get("deployments")
    if isinstance(deployments, list) and deployments:
        first = deployments[0]
        if isinstance(first, dict):
            uuid = first.get("deployment_uuid") or first.get("uuid") or first.get("id")
            if not result.get("message") and first.get("message"):
                result["message"] = first["message"]
            if uuid:
                return str(uuid)
    flat = result.get("deployment_uuid") or result.get("uuid")
    return str(flat) if flat else ""


def _normalize_database(raw: dict[str, Any]) -> CoolifyDatabase:
    return CoolifyDatabase(
        id=str(raw.get("uuid") or raw.get("id") or "unknown"),
        name=str(raw.get("name") or "Unnamed DB"),
        type=str(raw.get("type") or raw.get("database_type") or ""),
        status=str(raw.get("status") or "unknown"),
        internal_db_url=str(raw.get("internal_db_url") or ""),
        public_port=str(raw.get("public_port") or ""),
        image=str(raw.get("image") or ""),
        created_at=str(raw.get("created_at") or ""),
        description=str(raw.get("description") or ""),
        limits_memory=str(raw.get("limits_memory") or ""),
        limits_cpu=str(raw.get("limits_cpu") or ""),
    )


def _normalize_service(raw: dict[str, Any]) -> CoolifyService:
    return CoolifyService(
        id=str(raw.get("uuid") or raw.get("id") or "unknown"),
        name=str(raw.get("name") or "Unnamed"),
        type=str(raw.get("type") or ""),
        status=str(raw.get("status") or "unknown"),
        description=str(raw.get("description") or ""),
        created_at=str(raw.get("created_at") or ""),
        fqdn=str(raw.get("fqdn") or ""),
    )


def _normalize_scheduled_task(raw: dict[str, Any]) -> CoolifyScheduledTask:
    return CoolifyScheduledTask(
        id=str(raw.get("uuid") or raw.get("id") or raw.get("name") or "unknown"),
        name=str(raw.get("name") or raw.get("title") or "Scheduled Task"),
        command=str(raw.get("command") or raw.get("container_command") or ""),
        frequency=str(raw.get("frequency") or raw.get("cron") or raw.get("interval") or ""),
        status=str(raw.get("status") or raw.get("state") or ""),
        raw=raw,
    )


def _normalize_storage(raw: dict[str, Any]) -> CoolifyStorage:
    return CoolifyStorage(
        id=str(raw.get("uuid") or raw.get("id") or raw.get("name") or "unknown"),
        name=str(raw.get("name") or raw.get("mount_path") or raw.get("host_path") or "Storage"),
        mount_path=str(raw.get("mount_path") or raw.get("destination") or ""),
        host_path=str(raw.get("host_path") or raw.get("source") or ""),
        content=str(raw.get("content") or ""),
        raw=raw,
    )


def _normalize_server(raw: dict[str, Any]) -> CoolifyServer:
    return CoolifyServer(
        id=str(raw.get("uuid") or raw.get("id") or "unknown"),
        name=str(raw.get("name") or "Unknown"),
        ip=str(raw.get("ip") or ""),
        user=str(raw.get("user") or ""),
        description=str(raw.get("description") or ""),
        is_reachable=bool(raw.get("settings", {}).get("is_reachable", False) if isinstance(raw.get("settings"), dict) else raw.get("is_reachable", False)),
        is_usable=bool(raw.get("settings", {}).get("is_usable", False) if isinstance(raw.get("settings"), dict) else raw.get("is_usable", False)),
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

    # ── Applications ──────────────────────────────────────────────

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

    async def get_project(self, project_uuid: str) -> dict[str, Any]:
        if not self.is_configured() or not project_uuid:
            return {}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/projects/{project_uuid}",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {}

    async def environment_project_map(self, refresh: bool = False) -> dict[int, dict[str, str]]:
        """Map Coolify ``environment_id`` → its project ``{uuid, name, environment}``.

        The applications list only carries ``environment_id``; the projects list
        omits environments — so this resolves the link by fetching each project's
        detail. Cached (provider TTL) since project structure changes rarely.
        """
        if not self.is_configured():
            return {}
        settings = get_settings()

        async def fetch() -> dict[int, dict[str, str]]:
            mapping: dict[int, dict[str, str]] = {}
            for project in await self.list_projects():
                uuid = str(project.get("uuid") or "")
                name = str(project.get("name") or "Project")
                detail = await self.get_project(uuid)
                for env in detail.get("environments") or []:
                    env_id = env.get("id")
                    if env_id is not None:
                        mapping[int(env_id)] = {
                            "uuid": uuid,
                            "name": name,
                            "environment": str(env.get("name") or ""),
                        }
            return mapping

        if refresh:
            await self.cache.delete("coolify:env_project_map")
        return await self.cache.get_or_set(
            "coolify:env_project_map",
            settings.provider_cache_ttl_seconds,
            fetch,
        )

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
            apps = [normalize_coolify_resource(item) for item in items]
            # Attach the owning Coolify project so the UI can group apps under it
            # (tenant > project > deployment). Falls back to the app itself when
            # the map is unavailable, so grouping degrades to one-app-per-project.
            env_map = await self.environment_project_map()
            for app in apps:
                info = env_map.get(app.environment_id)
                if info:
                    app.project_uuid = info["uuid"]
                    app.project_name = info["name"]
                    if info.get("environment"):
                        app.environment = info["environment"]
            return apps

        if refresh:
            await self.cache.delete("coolify:applications")
        return await self.cache.get_or_set(
            "coolify:applications",
            settings.provider_cache_ttl_seconds,
            fetch,
        )

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

    async def get_application_raw(self, application_uuid: str) -> dict[str, Any]:
        """Get full raw API response for an application (for settings editing)."""
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

    async def update_application(self, application_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="PATCH",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}",
            headers=self.headers(),
            json_body=data,
        )
        await self.cache.delete("coolify:applications")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def delete_application(self, application_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="DELETE",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}",
            headers=self.headers(),
        )
        await self.cache.delete("coolify:applications")
        return payload if isinstance(payload, dict) else {"ok": True}

    # ── Application Actions ───────────────────────────────────────

    async def deploy_application(self, application_uuid: str, force: bool = False, tag: str = "") -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        params: dict[str, str] = {"uuid": application_uuid, "force": str(force).lower()}
        if tag:
            params["tag"] = tag
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/deploy",
            headers=self.headers(),
            params=params,
        )
        await self.cache.delete("coolify:applications")
        result = payload if isinstance(payload, dict) else {"ok": True, "payload": payload}
        result.setdefault("ok", True)
        deployment_id = _extract_deployment_uuid(result)
        if deployment_id:
            result["deployment_id"] = deployment_id
        return result

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

    # ── Logs & Execute ────────────────────────────────────────────

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

    async def execute_command(self, application_uuid: str, command: str) -> str:
        """Execute a command inside the application's container."""
        if not self.is_configured():
            return "Coolify is not configured."
        try:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="POST",
                url=f"{self.base_url}/api/v1/applications/{application_uuid}/execute",
                headers=self.headers(),
                json_body={"command": command},
            )
            if isinstance(payload, dict):
                return str(payload.get("output", payload.get("result", str(payload))))
            return str(payload)
        except Exception as exc:
            return f"Command execution failed: {exc}"

    # ── Environment Variables ─────────────────────────────────────

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

    async def create_env(self, application_uuid: str, key: str, value: str, is_preview: bool = False, is_build_time: bool = False) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/envs",
            headers=self.headers(),
            json_body={
                "key": key,
                "value": value,
                "is_preview": is_preview,
                "is_build_time": is_build_time,
            },
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def update_env(self, application_uuid: str, key: str, value: str, is_preview: bool = False, is_build_time: bool = False) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="PATCH",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/envs",
            headers=self.headers(),
            json_body={
                "key": key,
                "value": value,
                "is_preview": is_preview,
                "is_build_time": is_build_time,
            },
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def delete_env(self, application_uuid: str, env_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="DELETE",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/envs/{env_uuid}",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def list_scheduled_tasks(self, application_uuid: str) -> list[CoolifyScheduledTask]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/scheduled-tasks",
            headers=self.headers(),
        )
        items = payload.get("data", payload) if isinstance(payload, dict) else payload
        return [_normalize_scheduled_task(item) for item in items if isinstance(item, dict)]

    async def create_scheduled_task(self, application_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/scheduled-tasks",
            headers=self.headers(),
            json_body=data,
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def update_scheduled_task(self, application_uuid: str, task_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="PATCH",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/scheduled-tasks/{task_uuid}",
            headers=self.headers(),
            json_body=data,
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def delete_scheduled_task(self, application_uuid: str, task_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="DELETE",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/scheduled-tasks/{task_uuid}",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def list_scheduled_task_executions(self, application_uuid: str, task_uuid: str) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/scheduled-tasks/{task_uuid}/executions",
            headers=self.headers(),
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data", [])
        return []

    async def list_storages(self, application_uuid: str) -> list[CoolifyStorage]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/storages",
            headers=self.headers(),
        )
        items = payload.get("data", payload) if isinstance(payload, dict) else payload
        return [_normalize_storage(item) for item in items if isinstance(item, dict)]

    async def create_storage(self, application_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/storages",
            headers=self.headers(),
            json_body=data,
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def update_storage(self, application_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="PATCH",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/storages",
            headers=self.headers(),
            json_body=data,
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def delete_storage(self, application_uuid: str, storage_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="DELETE",
            url=f"{self.base_url}/api/v1/applications/{application_uuid}/storages/{storage_uuid}",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    # ── Deployments ───────────────────────────────────────────────

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

    async def get_deployment(self, deployment_uuid: str) -> CoolifyDeployment | None:
        if not self.is_configured():
            return None
        try:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="GET",
                url=f"{self.base_url}/api/v1/deployments/{deployment_uuid}",
                headers=self.headers(),
            )
            if isinstance(payload, dict):
                return normalize_coolify_deployment(payload)
            return None
        except Exception:
            return None

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
        # Coolify wraps the list as {"count": N, "deployments": [...]}; tolerate a bare
        # list or a "data"-wrapped shape too. Never fall back to the dict itself, or we
        # would iterate its keys and synthesize bogus "count"/"deployments" entries.
        if isinstance(payload, dict):
            items = payload.get("deployments") or payload.get("data") or []
        else:
            items = payload or []
        results: list[CoolifyDeployment] = []
        for item in items:
            if isinstance(item, str):
                results.append(CoolifyDeployment(id=item, status="unknown"))
            elif isinstance(item, dict):
                results.append(normalize_coolify_deployment(item))
        return results

    # ── Databases ─────────────────────────────────────────────────

    async def list_databases(self, refresh: bool = False) -> list[CoolifyDatabase]:
        if not self.is_configured():
            return []
        settings = get_settings()

        async def fetch() -> list[CoolifyDatabase]:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="GET",
                url=f"{self.base_url}/api/v1/databases",
                headers=self.headers(),
            )
            items = payload.get("data", payload) if isinstance(payload, dict) else payload
            return [_normalize_database(item) for item in items if isinstance(item, dict)]

        if refresh:
            await self.cache.delete("coolify:databases")
        return await self.cache.get_or_set("coolify:databases", settings.provider_cache_ttl_seconds, fetch)

    async def get_database(self, database_uuid: str) -> CoolifyDatabase | None:
        if not self.is_configured():
            return None
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}",
            headers=self.headers(),
        )
        if isinstance(payload, dict) and payload.get("uuid"):
            return _normalize_database(payload)
        return None

    async def start_database(self, database_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client, service="Coolify", method="GET",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/start", headers=self.headers(),
        )
        await self.cache.delete("coolify:databases")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def stop_database(self, database_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client, service="Coolify", method="GET",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/stop", headers=self.headers(),
        )
        await self.cache.delete("coolify:databases")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def restart_database(self, database_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client, service="Coolify", method="GET",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/restart", headers=self.headers(),
        )
        await self.cache.delete("coolify:databases")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def provision_database(
        self,
        db_type: str,
        server_uuid: str,
        project_uuid: str,
        environment_name: str,
        name: str,
        **opts: Any,
    ) -> dict[str, Any]:
        """Provision a new managed database on Coolify.

        Coolify v4 uses type-specific POST endpoints:
        POST /api/v1/databases/{postgresql|mysql|mariadb|mongodb|redis|keydb|dragonfly|clickhouse}

        Required fields per v4 spec: server_uuid, project_uuid, environment_name, name.

        db_type is validated here against DB_TYPE_ALLOWLIST as a client-layer invariant
        (defense-in-depth — the service layer also validates before calling this method).
        """
        # Fix 3: client-layer invariant — rejects unsupported types regardless of caller.
        if db_type not in DB_TYPE_ALLOWLIST:
            raise ValueError(f"Unsupported database type: {db_type}")
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        body: dict[str, Any] = {
            "server_uuid": server_uuid,
            "project_uuid": project_uuid,
            "environment_name": environment_name,
            "name": name,
            **opts,
        }
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/databases/{db_type}",
            headers=self.headers(),
            json_body=body,
        )
        await self.cache.delete("coolify:databases")
        return payload if isinstance(payload, dict) else {"ok": True, "payload": payload}

    async def list_database_backups(self, database_uuid: str) -> list[dict[str, Any]]:
        """List scheduled backup configs for a database (GET /databases/{uuid}/backups)."""
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/backups",
            headers=self.headers(),
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data", [])
        return []

    async def create_database_backup(self, database_uuid: str, **config: Any) -> dict[str, Any]:
        """Create a backup config for a database (POST /databases/{uuid}/backups).

        Common config fields per v4 spec:
        - frequency: cron string (e.g. "0 2 * * *")
        - retention_days: int
        - s3_storage_id: str (UUID of pre-configured S3 storage in Coolify)
        """
        if not self.is_configured():
            return {"ok": False, "message": "Coolify is not configured."}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="POST",
            url=f"{self.base_url}/api/v1/databases/{database_uuid}/backups",
            headers=self.headers(),
            json_body=dict(config),
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    # ── Services ──────────────────────────────────────────────────

    async def list_services(self, refresh: bool = False) -> list[CoolifyService]:
        if not self.is_configured():
            return []
        settings = get_settings()

        async def fetch() -> list[CoolifyService]:
            payload = await request_json(
                self.http_client,
                service="Coolify",
                method="GET",
                url=f"{self.base_url}/api/v1/services",
                headers=self.headers(),
            )
            items = payload.get("data", payload) if isinstance(payload, dict) else payload
            return [_normalize_service(item) for item in items if isinstance(item, dict)]

        if refresh:
            await self.cache.delete("coolify:services")
        return await self.cache.get_or_set("coolify:services", settings.provider_cache_ttl_seconds, fetch)

    async def start_service(self, service_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client, service="Coolify", method="GET",
            url=f"{self.base_url}/api/v1/services/{service_uuid}/start", headers=self.headers(),
        )
        await self.cache.delete("coolify:services")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def stop_service(self, service_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client, service="Coolify", method="GET",
            url=f"{self.base_url}/api/v1/services/{service_uuid}/stop", headers=self.headers(),
        )
        await self.cache.delete("coolify:services")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def restart_service(self, service_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client, service="Coolify", method="GET",
            url=f"{self.base_url}/api/v1/services/{service_uuid}/restart", headers=self.headers(),
        )
        await self.cache.delete("coolify:services")
        return payload if isinstance(payload, dict) else {"ok": True}

    # ── Servers ───────────────────────────────────────────────────

    async def list_servers(self) -> list[CoolifyServer]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/servers",
            headers=self.headers(),
        )
        items = payload if isinstance(payload, list) else (payload.get("data", []) if isinstance(payload, dict) else [])
        return [_normalize_server(item) for item in items if isinstance(item, dict)]

    async def get_server_resources(self, server_uuid: str) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/servers/{server_uuid}/resources",
            headers=self.headers(),
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data", [])
        return []

    async def get_server_domains(self, server_uuid: str) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/servers/{server_uuid}/domains",
            headers=self.headers(),
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data", [])
        return []

    async def validate_server(self, server_uuid: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False}
        payload = await request_json(
            self.http_client,
            service="Coolify",
            method="GET",
            url=f"{self.base_url}/api/v1/servers/{server_uuid}/validate",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {"ok": True}