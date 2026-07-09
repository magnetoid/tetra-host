"""Apps — install & control pre-defined Docker containers via the Tetra Engine (tenant-scoped).

Sits on top of the independent Docker engine (``app/services/docker_engine.py``) and the compose
catalog (``app/services/app_catalog.py``). No Coolify in the data path. Installed apps are recorded as
``TenantResource`` rows (provider=docker, resource_type=app) so visibility/control is tenant-isolated.
"""

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.config import get_settings
from app.models import Deployment, TenantResource
from app.models.deployment import STATUS_READY
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services.app_catalog import (
    AppCatalog,
    AppTemplate,
    normalize_compose_for_engine,
    render_service_vars,
)
from app.services.docker_engine import DockerEngine, DockerEngineError, sanitize_project_name
from app.services.edge import apply_edge
from app.services.quota import Allocation, QuotaService
from app.services.compute import ComputeSample, parse_compute_samples
from app.services.limits import apply_resource_limits
from app.services.tenant_resources import TenantResourceFilter


class InstalledApp(BaseModel):
    project: str
    name: str
    template: str = ""
    status: str = "unknown"
    domain: str = ""


def _stack_status_map(stacks: list[dict]) -> dict[str, str]:
    """Map compose project name -> status from `docker compose ls --format json`."""
    status: dict[str, str] = {}
    for stack in stacks:
        name = str(stack.get("Name") or stack.get("name") or "")
        if name:
            status[name] = str(stack.get("Status") or stack.get("status") or "")
    return status


class AppsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        settings = get_settings()
        self.engine = DockerEngine(docker_bin=settings.docker_bin)
        self.catalog = AppCatalog.from_request(request)
        self.base_domain = settings.apps_base_domain
        self.actions_enabled = settings.enable_provider_actions

    def _require_actions(self) -> None:
        if not self.actions_enabled:
            raise DockerEngineError(
                message="Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false).",
                code=403,
            )

    async def list_catalog(
        self, *, search: str | None = None, category: str | None = None
    ) -> list[AppTemplate]:
        templates = await self.catalog.list_templates()
        if category:
            templates = [t for t in templates if t.category == category]
        if search:
            needle = search.strip().lower()
            templates = [
                t for t in templates
                if needle in t.name.lower()
                or needle in t.description.lower()
                or any(needle in tag.lower() for tag in t.tags)
            ]
        return templates

    async def _ensure_app_access(
        self, session: AsyncSession, tenant_id: str | None, project: str
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_DOCKER, resource_type=RESOURCE_TYPE_APP, external_id=project
        )
        if not allowed:
            raise DockerEngineError(message="App is not assigned to this tenant.", code=403)

    async def list_installed_for_tenant(
        self, session: AsyncSession, tenant_id: str | None
    ) -> list[InstalledApp]:
        rows = list(
            (
                await session.scalars(
                    select(TenantResource).where(
                        TenantResource.tenant_id == (tenant_id or ""),
                        TenantResource.provider == PROVIDER_DOCKER,
                        TenantResource.resource_type == RESOURCE_TYPE_APP,
                    )
                )
            ).all()
        )
        status_map: dict[str, str] = {}
        try:
            status_map = _stack_status_map(await self.engine.list_stacks())
        except DockerEngineError:
            status_map = {}
        return [
            InstalledApp(
                project=row.external_id,
                name=row.display_name or row.external_id,
                status=status_map.get(row.external_id, "unknown"),
                domain=f"{row.external_id}.{self.base_domain}" if self.base_domain else "",
            )
            for row in rows
        ]

    async def install_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        slug: str,
        name: str | None = None,
        domain: str | None = None,
    ) -> dict:
        self._require_actions()
        template = await self.catalog.get_template(slug)
        if template is None:
            raise DockerEngineError(message=f"Unknown app template '{slug}'.", code=404)
        compose = normalize_compose_for_engine(template.decoded_compose())
        if not compose:
            raise DockerEngineError(message="Template has no compose definition.", code=422)

        project = sanitize_project_name(name or slug)
        existing = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == (tenant_id or ""),
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == project,
            )
        )
        if existing is not None:
            raise DockerEngineError(message=f"App '{project}' is already installed.", code=409)

        resolved_domain = domain or (f"{project}.{self.base_domain}" if self.base_domain else "")
        # Attach Caddy routing labels + edge network (no-op unless the edge is configured).
        compose = apply_edge(compose, project=project, port=template.port)

        # Atomically reserve a quota slot BEFORE the build starts.
        # QuotaExceeded is intentionally NOT caught here — it must bubble up to the 402 handler.
        settings = get_settings()
        allocation = Allocation(
            cpu_millicores=settings.default_app_cpu_millicores,
            mem_mb=settings.default_app_mem_mb,
            disk_mb=settings.default_app_disk_mb,
        )
        # Hard cgroup caps so the stack can't starve the shared host.
        compose = apply_resource_limits(
            compose, cpu_millicores=allocation.cpu_millicores, mem_mb=allocation.mem_mb
        )
        env = render_service_vars(compose, domain=resolved_domain)
        quota = QuotaService(session, tenant_id or "")
        await quota.check_and_reserve(project, allocation, template.name)

        try:
            await self.engine.deploy_stack(project, compose, env)
        except Exception:
            # Release the reservation so a failed install leaves no orphan slot.
            # Catch ALL exceptions (not just DockerEngineError) to prevent quota leaks
            # from network errors, TimeoutError, OSError, etc.
            await quota.release(project)
            raise

        # Record the install as a Deployment so it appears in the deployments history
        # alongside git deploys. builder="app" marks it as a marketplace/compose install
        # (no git fields, no rollback); the stack came up, so it's ready.
        port = int(template.port) if str(template.port).isdigit() else 0
        live_line = f"✓ live at https://{resolved_domain}" if resolved_domain else "✓ running"
        session.add(
            Deployment(
                tenant_id=tenant_id or "",
                project=project,
                status=STATUS_READY,
                builder="app",
                image=template.slug,
                domain=resolved_domain,
                port=port,
                log=f"→ installing {template.name}\n{live_line}",
            )
        )
        await session.flush()

        return {"ok": True, "project": project, "domain": resolved_domain}

    async def control_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str, action: str
    ) -> dict:
        self._require_actions()
        await self._ensure_app_access(session, tenant_id, project)
        if action == "start":
            return await self.engine.start_stack(project)
        if action == "stop":
            return await self.engine.stop_stack(project)
        raise DockerEngineError(message=f"Unknown action '{action}'.", code=400)

    async def remove_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str, *, volumes: bool = False
    ) -> dict:
        self._require_actions()
        await self._ensure_app_access(session, tenant_id, project)
        result = await self.engine.remove_stack(project, volumes=volumes)
        clean_project = sanitize_project_name(project)
        await session.execute(
            delete(TenantResource).where(
                TenantResource.tenant_id == (tenant_id or ""),
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == clean_project,
            )
        )
        # Drop the app's deployment-history entry so it doesn't linger as "ready".
        await session.execute(
            delete(Deployment).where(
                Deployment.tenant_id == (tenant_id or ""),
                Deployment.project == clean_project,
                Deployment.builder == "app",
            )
        )
        return result

    async def logs_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str, *, tail: int = 200
    ) -> str:
        await self._ensure_app_access(session, tenant_id, project)
        return await self.engine.logs(project, tail=tail)

    async def compute_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, project: str
    ) -> list[ComputeSample]:
        """Live per-container CPU/mem/net snapshot for a tenant's app (Vercel-style)."""
        await self._ensure_app_access(session, tenant_id, project)
        raw = await self.engine.stats_for_project(project)
        return parse_compute_samples(raw)
