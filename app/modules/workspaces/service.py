"""Team → project → environment → app: queries, writes and the index sync.

The hierarchy tables index workloads that live elsewhere (engine stacks, Coolify
applications). ``sync`` keeps the index current and is idempotent; it runs before every
listing, so nothing has to remember to call it when a deploy or an import happens.

Placement is owned by the user: sync only *creates* an app row (in the environment its
source suggests) and refreshes its name and domain. Once a row exists, moving it to
another environment is never undone by a later sync.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminUser,
    AuditEvent,
    Deployment,
    Environment,
    ImportRun,
    PreviewEnv,
    Tenant,
    TenantResource,
    WorkspaceApp,
    WorkspaceProject,
)
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.models.import_run import IMPORT_LIVE
from app.models.team import ROLE_ADMIN
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.models.workspace import (
    DRIVER_COOLIFY,
    DRIVER_ENGINE,
    ENV_PREVIEW,
    ENV_PRODUCTION,
    ENV_STAGING,
    ENVIRONMENT_KINDS,
)
from app.services.coolify import CoolifyApplication

logger = logging.getLogger(__name__)

WRITE_ROLES = frozenset({ROLE_PLATFORM_ADMIN, ROLE_OWNER, ROLE_ADMIN})
_PRODUCTION_NAMES = {"production", "prod", "main", "live"}


class WorkspaceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def slugify(value: str, *, fallback: str = "default", max_length: int = 63) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:max_length].strip("-")
    return slug or fallback


@dataclass(frozen=True)
class ProjectRow:
    project: WorkspaceProject
    environments: int
    apps: int


@dataclass(frozen=True)
class EnvironmentRow:
    environment: Environment
    apps: int


@dataclass(frozen=True)
class AppRow:
    app: WorkspaceApp
    environment: Environment
    project: WorkspaceProject
    tenant: Tenant


@dataclass(frozen=True)
class TeamCounts:
    projects: int
    environments: int
    apps: int
    members: int


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Access ────────────────────────────────────────────────────

    async def resolve_team(self, admin: AdminUser, team_ref: str) -> Tenant:
        """The team by slug or id. Anyone but a platform admin only sees their own team;
        another team answers 404 so team slugs cannot be probed."""
        tenant = await self.session.scalar(
            select(Tenant).where((Tenant.slug == team_ref) | (Tenant.id == team_ref))
        )
        if tenant is None or (admin.role != ROLE_PLATFORM_ADMIN and tenant.id != admin.tenant_id):
            raise WorkspaceError("Team not found.", 404)
        return tenant

    async def visible_teams(self, admin: AdminUser) -> list[Tenant]:
        query = select(Tenant).order_by(Tenant.name)
        if admin.role != ROLE_PLATFORM_ADMIN:
            query = query.where(Tenant.id == admin.tenant_id)
        return list((await self.session.scalars(query)).all())

    @staticmethod
    def ensure_can_write(admin: AdminUser) -> None:
        if admin.role not in WRITE_ROLES:
            raise WorkspaceError("Only team owners and admins can change projects.", 403)

    # ── Teams ─────────────────────────────────────────────────────

    async def team_counts(self, tenant_id: str) -> TeamCounts:
        async def count(model, *where) -> int:
            return int(await self.session.scalar(select(func.count()).select_from(model).where(*where)) or 0)

        return TeamCounts(
            projects=await count(WorkspaceProject, WorkspaceProject.tenant_id == tenant_id),
            environments=await count(Environment, Environment.tenant_id == tenant_id),
            apps=await count(WorkspaceApp, WorkspaceApp.tenant_id == tenant_id),
            members=await count(AdminUser, AdminUser.tenant_id == tenant_id),
        )

    # ── Projects ──────────────────────────────────────────────────

    async def list_projects(self, tenant_id: str) -> list[ProjectRow]:
        env_counts = dict(
            (await self.session.execute(
                select(Environment.project_id, func.count())
                .where(Environment.tenant_id == tenant_id)
                .group_by(Environment.project_id)
            )).all()
        )
        app_counts = dict(
            (await self.session.execute(
                select(Environment.project_id, func.count(WorkspaceApp.id))
                .join(WorkspaceApp, WorkspaceApp.environment_id == Environment.id)
                .where(Environment.tenant_id == tenant_id)
                .group_by(Environment.project_id)
            )).all()
        )
        projects = await self.session.scalars(
            select(WorkspaceProject)
            .where(WorkspaceProject.tenant_id == tenant_id)
            .order_by(WorkspaceProject.name)
        )
        return [
            ProjectRow(p, int(env_counts.get(p.id, 0)), int(app_counts.get(p.id, 0)))
            for p in projects.all()
        ]

    async def get_project(self, tenant_id: str, project_ref: str) -> WorkspaceProject:
        project = await self.session.scalar(
            select(WorkspaceProject).where(
                WorkspaceProject.tenant_id == tenant_id,
                (WorkspaceProject.slug == project_ref) | (WorkspaceProject.id == project_ref),
            )
        )
        if project is None:
            raise WorkspaceError("Project not found.", 404)
        return project

    async def create_project(
        self, tenant_id: str, *, name: str, slug: str | None, actor: str
    ) -> WorkspaceProject:
        slug = slugify(slug or name, fallback="project")
        if await self._project_by_slug(tenant_id, slug) is not None:
            raise WorkspaceError(f"A project named '{slug}' already exists.", 409)
        project = WorkspaceProject(tenant_id=tenant_id, slug=slug, name=name.strip())
        self.session.add(project)
        await self.session.flush()
        self.session.add(Environment(
            tenant_id=tenant_id, project_id=project.id, slug=ENV_PRODUCTION,
            name="Production", kind=ENV_PRODUCTION,
        ))
        self._audit(actor, "project.create", f"{tenant_id}/{slug}")
        await self.session.flush()
        return project

    async def rename_project(self, project: WorkspaceProject, *, name: str, actor: str) -> None:
        project.name = name.strip()
        self._audit(actor, "project.rename", f"{project.tenant_id}/{project.slug}", name)
        await self.session.flush()

    async def delete_project(self, project: WorkspaceProject, *, actor: str) -> None:
        apps = await self.session.scalar(
            select(func.count(WorkspaceApp.id))
            .join(Environment, WorkspaceApp.environment_id == Environment.id)
            .where(Environment.project_id == project.id)
        )
        if apps:
            raise WorkspaceError("Move or remove the project's apps before deleting it.", 409)
        for env in (await self.session.scalars(
            select(Environment).where(Environment.project_id == project.id)
        )).all():
            await self.session.delete(env)
        await self.session.delete(project)
        self._audit(actor, "project.delete", f"{project.tenant_id}/{project.slug}")
        await self.session.flush()

    # ── Environments ──────────────────────────────────────────────

    async def list_environments(self, project: WorkspaceProject) -> list[EnvironmentRow]:
        counts = dict(
            (await self.session.execute(
                select(WorkspaceApp.environment_id, func.count())
                .join(Environment, WorkspaceApp.environment_id == Environment.id)
                .where(Environment.project_id == project.id)
                .group_by(WorkspaceApp.environment_id)
            )).all()
        )
        envs = await self.session.scalars(
            select(Environment).where(Environment.project_id == project.id)
        )
        order = {kind: i for i, kind in enumerate(ENVIRONMENT_KINDS)}
        rows = [EnvironmentRow(e, int(counts.get(e.id, 0))) for e in envs.all()]
        return sorted(rows, key=lambda r: (order.get(r.environment.kind, 9), r.environment.name))

    async def get_environment(self, project: WorkspaceProject, env_ref: str) -> Environment:
        env = await self.session.scalar(
            select(Environment).where(
                Environment.project_id == project.id,
                (Environment.slug == env_ref) | (Environment.id == env_ref),
            )
        )
        if env is None:
            raise WorkspaceError("Environment not found.", 404)
        return env

    async def create_environment(
        self, project: WorkspaceProject, *, name: str, kind: str, slug: str | None, actor: str
    ) -> Environment:
        if kind not in ENVIRONMENT_KINDS:
            raise WorkspaceError(f"kind must be one of {', '.join(ENVIRONMENT_KINDS)}.", 422)
        slug = slugify(slug or name, fallback=kind)
        if await self._env_by_slug(project.id, slug) is not None:
            raise WorkspaceError(f"An environment named '{slug}' already exists.", 409)
        env = Environment(
            tenant_id=project.tenant_id, project_id=project.id, slug=slug,
            name=name.strip(), kind=kind,
        )
        self.session.add(env)
        self._audit(actor, "environment.create", f"{project.tenant_id}/{project.slug}/{slug}")
        await self.session.flush()
        return env

    async def delete_environment(self, env: Environment, *, actor: str) -> None:
        apps = await self.session.scalar(
            select(func.count(WorkspaceApp.id)).where(WorkspaceApp.environment_id == env.id)
        )
        if apps:
            raise WorkspaceError("Move the environment's apps before deleting it.", 409)
        await self.session.delete(env)
        self._audit(actor, "environment.delete", f"{env.tenant_id}/{env.project_id}/{env.slug}")
        await self.session.flush()

    # ── Apps ──────────────────────────────────────────────────────

    async def list_apps(
        self,
        *,
        tenant_id: str | None,
        project_id: str | None = None,
        environment_id: str | None = None,
    ) -> list[AppRow]:
        """Apps with their placement. ``tenant_id=None`` is the platform-wide view and is
        only reachable through a platform-admin route."""
        query = (
            select(WorkspaceApp, Environment, WorkspaceProject, Tenant)
            .join(Environment, WorkspaceApp.environment_id == Environment.id)
            .join(WorkspaceProject, Environment.project_id == WorkspaceProject.id)
            .join(Tenant, WorkspaceApp.tenant_id == Tenant.id)
            .order_by(Tenant.name, WorkspaceProject.name, Environment.name, WorkspaceApp.name)
        )
        if tenant_id is not None:
            query = query.where(WorkspaceApp.tenant_id == tenant_id)
        if project_id is not None:
            query = query.where(Environment.project_id == project_id)
        if environment_id is not None:
            query = query.where(WorkspaceApp.environment_id == environment_id)
        return [AppRow(*row) for row in (await self.session.execute(query)).all()]

    async def move_app(
        self, tenant_id: str, app_id: str, *, environment_id: str, actor: str
    ) -> WorkspaceApp:
        app = await self.session.scalar(
            select(WorkspaceApp).where(WorkspaceApp.id == app_id, WorkspaceApp.tenant_id == tenant_id)
        )
        if app is None:
            raise WorkspaceError("App not found.", 404)
        env = await self.session.scalar(
            select(Environment).where(Environment.id == environment_id, Environment.tenant_id == tenant_id)
        )
        if env is None:
            raise WorkspaceError("Environment not found.", 404)
        app.environment_id = env.id
        self._audit(actor, "app.move", f"{tenant_id}/{app.name}", env.id)
        await self.session.flush()
        return app

    # ── Index sync ────────────────────────────────────────────────

    async def sync(self, coolify_apps: list[CoolifyApplication] | None) -> None:
        """Index engine workloads and (when the listing is available) Coolify apps.

        ``coolify_apps=None`` means Coolify could not be listed: its rows are left alone
        rather than pruned on a partial view."""
        imported = await self._live_imports()
        await self._sync_engine(imported)
        if coolify_apps is not None:
            await self._sync_coolify(coolify_apps, imported)
        await self.session.flush()

    async def _live_imports(self) -> dict[str, tuple[str, str]]:
        """Coolify uuid → (tenant, engine project) for apps the importer moved to the engine."""
        rows = await self.session.execute(
            select(ImportRun.source_ref, ImportRun.tenant_id, ImportRun.project).where(
                ImportRun.source == "coolify", ImportRun.state == IMPORT_LIVE
            )
        )
        return {ref: (tenant, project) for ref, tenant, project in rows.all()}

    async def _sync_engine(self, imported: dict[str, tuple[str, str]]) -> None:
        previews = (await self.session.scalars(select(PreviewEnv))).all()
        preview_stacks = {p.preview_project for p in previews}

        latest: dict[tuple[str, str], str] = {}
        rows = await self.session.execute(
            select(Deployment.tenant_id, Deployment.project, Deployment.domain)
            .order_by(Deployment.created_at)
        )
        for tenant_id, project, domain in rows.all():
            if project in preview_stacks:
                continue
            key = (tenant_id, project)
            latest[key] = domain or latest.get(key, "")

        by_stack = {project: (tenant, ref) for ref, (tenant, project) in imported.items()}
        for (tenant_id, stack), domain in latest.items():
            source = by_stack.get(stack)
            if source and source[0] == tenant_id:
                # Imported from Coolify: convert its existing row in place.
                row = await self._app(tenant_id, DRIVER_COOLIFY, source[1])
                if row is not None:
                    row.driver, row.external_id = DRIVER_ENGINE, stack
                    row.domain = domain or row.domain
                    continue
            project = await self._ensure_project(tenant_id, stack, stack)
            env = await self._ensure_env(project, ENV_PRODUCTION, "Production", ENV_PRODUCTION)
            await self._upsert_app(tenant_id, DRIVER_ENGINE, stack, env=env, name=stack, domain=domain)

        for preview in previews:
            project = await self._ensure_project(preview.tenant_id, preview.project, preview.project)
            env = await self._ensure_env(
                project, slugify(f"preview-{preview.branch}"), preview.branch, ENV_PREVIEW
            )
            await self._upsert_app(
                preview.tenant_id, DRIVER_ENGINE, preview.preview_project,
                env=env, name=preview.preview_project, domain=preview.domain,
            )

    async def _sync_coolify(
        self, coolify_apps: Iterable[CoolifyApplication], imported: dict[str, tuple[str, str]]
    ) -> None:
        owners = await self._coolify_owners()
        platform_tenant = await self.session.scalar(
            select(Tenant.id).where(Tenant.is_platform_scope.is_(True)).order_by(Tenant.created_at)
        )
        seen: set[tuple[str, str]] = set()
        for source in coolify_apps:
            if source.id in imported:
                continue  # the engine row stands for it now
            tenant_id = owners.get(source.id) or platform_tenant
            if not tenant_id:
                continue
            seen.add((tenant_id, source.id))
            project_name = source.project_name or "Coolify"
            project = await self._ensure_project(tenant_id, slugify(project_name, fallback="coolify"), project_name)
            env_name = source.environment or "production"
            kind = ENV_PRODUCTION if env_name.lower() in _PRODUCTION_NAMES else ENV_STAGING
            env = await self._ensure_env(project, slugify(env_name, fallback=kind), env_name, kind)
            await self._upsert_app(
                tenant_id, DRIVER_COOLIFY, source.id, env=env,
                name=source.name, domain=source.primary_domain,
            )

        # Prune rows for Coolify apps that no longer exist (or changed owner).
        stale = await self.session.scalars(select(WorkspaceApp).where(WorkspaceApp.driver == DRIVER_COOLIFY))
        for row in stale.all():
            # An imported app keeps its row until the engine side converts it.
            if (row.tenant_id, row.external_id) not in seen and row.external_id not in imported:
                await self.session.delete(row)

    async def _coolify_owners(self) -> dict[str, str]:
        rows = await self.session.execute(
            select(TenantResource.external_id, TenantResource.tenant_id)
            .where(
                TenantResource.provider == PROVIDER_COOLIFY,
                TenantResource.resource_type == RESOURCE_TYPE_SITE,
            )
            .order_by(TenantResource.created_at)
        )
        owners: dict[str, str] = {}
        for external_id, tenant_id in rows.all():
            owners.setdefault(external_id, tenant_id)
        return owners

    # ── Helpers ───────────────────────────────────────────────────

    async def _project_by_slug(self, tenant_id: str, slug: str) -> WorkspaceProject | None:
        return await self.session.scalar(
            select(WorkspaceProject).where(
                WorkspaceProject.tenant_id == tenant_id, WorkspaceProject.slug == slug
            )
        )

    async def _env_by_slug(self, project_id: str, slug: str) -> Environment | None:
        return await self.session.scalar(
            select(Environment).where(Environment.project_id == project_id, Environment.slug == slug)
        )

    async def _app(self, tenant_id: str, driver: str, external_id: str) -> WorkspaceApp | None:
        return await self.session.scalar(
            select(WorkspaceApp).where(
                WorkspaceApp.tenant_id == tenant_id,
                WorkspaceApp.driver == driver,
                WorkspaceApp.external_id == external_id,
            )
        )

    async def _ensure_project(self, tenant_id: str, slug: str, name: str) -> WorkspaceProject:
        slug = slugify(slug, fallback="project")
        project = await self._project_by_slug(tenant_id, slug)
        if project is None:
            project = WorkspaceProject(tenant_id=tenant_id, slug=slug, name=name)
            self.session.add(project)
            await self.session.flush()
        return project

    async def _ensure_env(
        self, project: WorkspaceProject, slug: str, name: str, kind: str
    ) -> Environment:
        env = await self._env_by_slug(project.id, slug)
        if env is None:
            env = Environment(
                tenant_id=project.tenant_id, project_id=project.id, slug=slug, name=name, kind=kind
            )
            self.session.add(env)
            await self.session.flush()
        return env

    async def _upsert_app(
        self, tenant_id: str, driver: str, external_id: str, *, env: Environment, name: str, domain: str
    ) -> WorkspaceApp:
        app = await self._app(tenant_id, driver, external_id)
        if app is None:
            app = WorkspaceApp(
                tenant_id=tenant_id, environment_id=env.id, driver=driver,
                external_id=external_id, name=name, domain=domain or "",
            )
            self.session.add(app)
            await self.session.flush()
        else:
            app.name = name or app.name
            app.domain = domain or app.domain
        return app

    def _audit(self, actor: str, action: str, target: str, details: str = "") -> None:
        self.session.add(AuditEvent(actor_email=actor, action=action, target=target, details=details))
