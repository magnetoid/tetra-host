"""Team → project → environment → app: queries, writes and the index sync.

The hierarchy tables index engine stacks (git deploys, marketplace installs, imports,
previews and managed databases) as services of a ``kind`` (ADR 0019). ``sync`` keeps the index current and is idempotent; it runs before every
listing, so nothing has to remember to call it when a deploy or an import happens.

Placement is owned by the user: a creation path that names an environment records the row
there right away (``place``); otherwise sync only *creates* an app row (in the environment its
source suggests) and refreshes its name and domain. Once a row exists, moving it to
another environment is never undone by a later sync.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminUser,
    AuditEvent,
    Deployment,
    Environment,
    ManagedDatabase,
    PreviewEnv,
    Tenant,
    TenantResource,
    WorkspaceApp,
    WorkspaceProject,
)
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.models.team import ROLE_ADMIN
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.models.workspace import (
    DRIVER_ENGINE,
    ENV_PREVIEW,
    ENV_PRODUCTION,
    ENVIRONMENT_KINDS,
    KIND_APP,
    KIND_DATABASE,
    SERVICE_KINDS,
)

# Where sync puts a database that was not created into an environment.
DATABASES_PROJECT = "databases"

logger = logging.getLogger(__name__)

WRITE_ROLES = frozenset({ROLE_PLATFORM_ADMIN, ROLE_OWNER, ROLE_ADMIN})


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
    # The managed database behind a kind=database service.
    database_id: str | None = None


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
            select(WorkspaceApp, Environment, WorkspaceProject, Tenant, ManagedDatabase.id)
            .join(Environment, WorkspaceApp.environment_id == Environment.id)
            .join(WorkspaceProject, Environment.project_id == WorkspaceProject.id)
            .join(Tenant, WorkspaceApp.tenant_id == Tenant.id)
            .outerjoin(
                ManagedDatabase,
                (ManagedDatabase.project == WorkspaceApp.external_id)
                & (WorkspaceApp.kind == KIND_DATABASE),
            )
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
        if app.kind == KIND_DATABASE:
            db = await self.session.scalar(
                select(ManagedDatabase).where(
                    ManagedDatabase.project == app.external_id,
                    ManagedDatabase.tenant_id == tenant_id,
                )
            )
            if db is not None:
                db.environment_id = env.id
        self._audit(actor, "app.move", f"{tenant_id}/{app.name}", env.id)
        await self.session.flush()
        return app

    # ── Placement at creation ─────────────────────────────────────

    async def require_environment(self, tenant_id: str | None, environment_id: str) -> Environment:
        """The environment a new service goes into; another team's answers 404."""
        env = await self.session.scalar(
            select(Environment).where(
                Environment.id == environment_id, Environment.tenant_id == (tenant_id or "")
            )
        )
        if env is None:
            raise WorkspaceError("Environment not found.", 404)
        return env

    async def place(
        self,
        env: Environment,
        external_id: str,
        *,
        kind: str,
        name: str,
        domain: str = "",
    ) -> WorkspaceApp:
        """Record a just-created service in ``env``. Called by the creation paths; later
        syncs keep it there."""
        if kind not in SERVICE_KINDS:
            raise WorkspaceError(f"kind must be one of {', '.join(SERVICE_KINDS)}.", 422)
        app = await self._app(env.tenant_id, DRIVER_ENGINE, external_id)
        if app is None:
            app = WorkspaceApp(
                tenant_id=env.tenant_id, environment_id=env.id, driver=DRIVER_ENGINE,
                external_id=external_id, kind=kind, name=name, domain=domain or "",
            )
            self.session.add(app)
        else:
            app.environment_id = env.id
            app.kind = kind
            app.name = name or app.name
        await self.session.flush()
        return app

    # ── Index sync ────────────────────────────────────────────────

    async def sync(self) -> None:
        """Index engine workloads: every git deploy, marketplace install and import
        (``TenantResource`` docker/app or a ``Deployment``), plus preview stacks. Rows for
        stacks that no longer exist are pruned; where a row sits is the user's choice and
        is never changed here."""
        previews = (await self.session.scalars(select(PreviewEnv))).all()
        preview_stacks = {p.preview_project for p in previews}

        latest: dict[tuple[str, str], str] = {}
        resources = await self.session.execute(
            select(TenantResource.tenant_id, TenantResource.external_id).where(
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
            )
        )
        for tenant_id, stack in resources.all():
            latest.setdefault((tenant_id, stack), "")
        rows = await self.session.execute(
            select(Deployment.tenant_id, Deployment.project, Deployment.domain)
            .order_by(Deployment.created_at)
        )
        for tenant_id, stack, domain in rows.all():
            key = (tenant_id, stack)
            latest[key] = domain or latest.get(key, "")

        live: set[tuple[str, str]] = set()
        for (tenant_id, stack), domain in latest.items():
            if stack in preview_stacks:
                continue
            live.add((tenant_id, stack))
            project = await self._ensure_project(tenant_id, stack, stack)
            env = await self._ensure_env(project, ENV_PRODUCTION, "Production", ENV_PRODUCTION)
            await self._upsert_app(tenant_id, DRIVER_ENGINE, stack, env=env, name=stack, domain=domain)

        for preview in previews:
            live.add((preview.tenant_id, preview.preview_project))
            project = await self._ensure_project(preview.tenant_id, preview.project, preview.project)
            env = await self._ensure_env(
                project, slugify(f"preview-{preview.branch}"), preview.branch, ENV_PREVIEW
            )
            await self._upsert_app(
                preview.tenant_id, DRIVER_ENGINE, preview.preview_project,
                env=env, name=preview.preview_project, domain=preview.domain,
            )

        databases = (await self.session.scalars(select(ManagedDatabase))).all()
        env_ids = {db.environment_id for db in databases if db.environment_id}
        envs = {
            e.id: e for e in (await self.session.scalars(
                select(Environment).where(Environment.id.in_(env_ids))
            )).all()
        } if env_ids else {}
        for db in databases:
            live.add((db.tenant_id, db.project))
            env = envs.get(db.environment_id or "")
            if env is None or env.tenant_id != db.tenant_id:
                project = await self._ensure_project(db.tenant_id, DATABASES_PROJECT, "Databases")
                env = await self._ensure_env(project, ENV_PRODUCTION, "Production", ENV_PRODUCTION)
            await self._upsert_app(
                db.tenant_id, DRIVER_ENGINE, db.project, env=env, name=db.name, domain="",
                kind=KIND_DATABASE,
            )

        # A removed app (or a rolled-back import) leaves no stack behind: drop its row.
        for row in (await self.session.scalars(select(WorkspaceApp))).all():
            if (row.tenant_id, row.external_id) not in live:
                await self.session.delete(row)
        await self.session.flush()

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
        self,
        tenant_id: str,
        driver: str,
        external_id: str,
        *,
        env: Environment,
        name: str,
        domain: str,
        kind: str = KIND_APP,
    ) -> WorkspaceApp:
        app = await self._app(tenant_id, driver, external_id)
        if app is None:
            app = WorkspaceApp(
                tenant_id=tenant_id, environment_id=env.id, driver=driver,
                external_id=external_id, kind=kind, name=name, domain=domain or "",
            )
            self.session.add(app)
            await self.session.flush()
        else:
            app.name = name or app.name
            app.domain = domain or app.domain
            app.kind = kind
        return app

    def _audit(self, actor: str, action: str, target: str, details: str = "") -> None:
        self.session.add(AuditEvent(actor_email=actor, action=action, target=target, details=details))
