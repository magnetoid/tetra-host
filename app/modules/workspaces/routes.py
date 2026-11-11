"""`/api/v1/teams/...` and `/api/v1/platform/apps` — the team → project → environment → app
hierarchy.

Own router (roadmap phase 1: new capabilities do not grow ``app/api/routes.py``). Every
team route resolves the team through ``WorkspaceService.resolve_team``: a platform admin
may address any team, everyone else only their own (others answer 404).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import get_current_api_admin, require_platform_admin
from app.db.session import get_db_session
from app.models import AdminUser, Environment, Tenant, WorkspaceProject
from app.modules.workspaces.service import AppRow, WorkspaceError, WorkspaceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])



# ── Contracts ─────────────────────────────────────────────────────


class TeamRef(BaseModel):
    id: str
    slug: str
    name: str


class TeamCountsOut(BaseModel):
    projects: int
    environments: int
    apps: int
    members: int


class TeamDetail(TeamRef):
    status: str
    is_platform_scope: bool
    plan_id: str | None
    created_at: datetime
    counts: TeamCountsOut


class ProjectRef(BaseModel):
    id: str
    slug: str
    name: str


class ProjectOut(ProjectRef):
    team: TeamRef
    environments: int
    apps: int
    created_at: datetime
    updated_at: datetime


class EnvironmentRef(BaseModel):
    id: str
    slug: str
    name: str
    kind: str


class EnvironmentOut(EnvironmentRef):
    project: ProjectRef
    apps: int


class WorkspaceAppOut(BaseModel):
    id: str
    name: str
    driver: str
    external_id: str
    domain: str
    team: TeamRef
    project: ProjectRef
    environment: EnvironmentRef
    updated_at: datetime


class WorkspaceProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=63)


class WorkspaceProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceEnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["production", "staging", "preview"] = "staging"
    slug: str | None = Field(default=None, max_length=63)


class WorkspaceAppMove(BaseModel):
    environment_id: str = Field(min_length=1, max_length=36)


# ── Mapping ───────────────────────────────────────────────────────


def _team_ref(tenant: Tenant) -> TeamRef:
    return TeamRef(id=tenant.id, slug=tenant.slug, name=tenant.name)


def _project_ref(project: WorkspaceProject) -> ProjectRef:
    return ProjectRef(id=project.id, slug=project.slug, name=project.name)


def _env_ref(env: Environment) -> EnvironmentRef:
    return EnvironmentRef(id=env.id, slug=env.slug, name=env.name, kind=env.kind)


def _app_out(row: AppRow) -> WorkspaceAppOut:
    return WorkspaceAppOut(
        id=row.app.id,
        name=row.app.name,
        driver=row.app.driver,
        external_id=row.app.external_id,
        domain=row.app.domain,
        team=_team_ref(row.tenant),
        project=_project_ref(row.project),
        environment=_env_ref(row.environment),
        updated_at=row.app.updated_at,
    )


def _http(exc: WorkspaceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ── Sync ──────────────────────────────────────────────────────────


async def _synced(session: AsyncSession) -> WorkspaceService:
    """The service, with the hierarchy index refreshed."""
    service = WorkspaceService(session)
    try:
        async with session.begin_nested():
            await service.sync()
    except IntegrityError:
        # A concurrent request indexed the same rows first; its result is just as good.
        logger.info("workspaces: concurrent sync, using the rows already indexed")
    return service


async def _team(
    team: str, admin: AdminUser, service: WorkspaceService
) -> Tenant:
    try:
        return await service.resolve_team(admin, team)
    except WorkspaceError as exc:
        raise _http(exc) from exc


# ── Teams ─────────────────────────────────────────────────────────


@router.get("/teams", response_model=list[TeamRef])
async def api_list_teams(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[TeamRef]:
    return [_team_ref(t) for t in await WorkspaceService(session).visible_teams(current_admin)]


@router.get("/teams/{team}", response_model=TeamDetail)
async def api_get_team(
    team: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> TeamDetail:
    service = await _synced(session)
    tenant = await _team(team, current_admin, service)
    counts = await service.team_counts(tenant.id)
    return TeamDetail(
        **_team_ref(tenant).model_dump(),
        status=tenant.status,
        is_platform_scope=tenant.is_platform_scope,
        plan_id=tenant.plan_id,
        created_at=tenant.created_at,
        counts=TeamCountsOut(**counts.__dict__),
    )


# ── Projects ──────────────────────────────────────────────────────


@router.get("/teams/{team}/projects", response_model=list[ProjectOut])
async def api_list_team_projects(
    team: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[ProjectOut]:
    service = await _synced(session)
    tenant = await _team(team, current_admin, service)
    return [
        ProjectOut(
            **_project_ref(row.project).model_dump(),
            team=_team_ref(tenant),
            environments=row.environments,
            apps=row.apps,
            created_at=row.project.created_at,
            updated_at=row.project.updated_at,
        )
        for row in await service.list_projects(tenant.id)
    ]


@router.post("/teams/{team}/projects", response_model=ProjectOut, status_code=201)
async def api_create_team_project(
    team: str,
    payload: WorkspaceProjectCreate,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ProjectOut:
    service = WorkspaceService(session)
    tenant = await _team(team, current_admin, service)
    try:
        service.ensure_can_write(current_admin)
        project = await service.create_project(
            tenant.id, name=payload.name, slug=payload.slug, actor=current_admin.email
        )
    except WorkspaceError as exc:
        raise _http(exc) from exc
    await session.commit()
    return ProjectOut(
        **_project_ref(project).model_dump(),
        team=_team_ref(tenant),
        environments=1,
        apps=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/teams/{team}/projects/{project}", response_model=ProjectOut)
async def api_get_team_project(
    team: str,
    project: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ProjectOut:
    service = await _synced(session)
    tenant = await _team(team, current_admin, service)
    try:
        found = await service.get_project(tenant.id, project)
    except WorkspaceError as exc:
        raise _http(exc) from exc
    envs = await service.list_environments(found)
    return ProjectOut(
        **_project_ref(found).model_dump(),
        team=_team_ref(tenant),
        environments=len(envs),
        apps=sum(e.apps for e in envs),
        created_at=found.created_at,
        updated_at=found.updated_at,
    )


@router.patch("/teams/{team}/projects/{project}", response_model=ProjectRef)
async def api_update_team_project(
    team: str,
    project: str,
    payload: WorkspaceProjectUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> ProjectRef:
    service = WorkspaceService(session)
    tenant = await _team(team, current_admin, service)
    try:
        service.ensure_can_write(current_admin)
        found = await service.get_project(tenant.id, project)
        await service.rename_project(found, name=payload.name, actor=current_admin.email)
    except WorkspaceError as exc:
        raise _http(exc) from exc
    await session.commit()
    return _project_ref(found)


@router.delete("/teams/{team}/projects/{project}", status_code=204)
async def api_delete_team_project(
    team: str,
    project: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> Response:
    service = WorkspaceService(session)
    tenant = await _team(team, current_admin, service)
    try:
        service.ensure_can_write(current_admin)
        found = await service.get_project(tenant.id, project)
        await service.delete_project(found, actor=current_admin.email)
    except WorkspaceError as exc:
        raise _http(exc) from exc
    await session.commit()
    return Response(status_code=204)


# ── Environments ──────────────────────────────────────────────────


@router.get("/teams/{team}/projects/{project}/environments", response_model=list[EnvironmentOut])
async def api_list_project_environments(
    team: str,
    project: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[EnvironmentOut]:
    service = await _synced(session)
    tenant = await _team(team, current_admin, service)
    try:
        found = await service.get_project(tenant.id, project)
    except WorkspaceError as exc:
        raise _http(exc) from exc
    return [
        EnvironmentOut(**_env_ref(row.environment).model_dump(), project=_project_ref(found), apps=row.apps)
        for row in await service.list_environments(found)
    ]


@router.post(
    "/teams/{team}/projects/{project}/environments",
    response_model=EnvironmentOut,
    status_code=201,
)
async def api_create_project_environment(
    team: str,
    project: str,
    payload: WorkspaceEnvironmentCreate,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> EnvironmentOut:
    service = WorkspaceService(session)
    tenant = await _team(team, current_admin, service)
    try:
        service.ensure_can_write(current_admin)
        found = await service.get_project(tenant.id, project)
        env = await service.create_environment(
            found, name=payload.name, kind=payload.kind, slug=payload.slug, actor=current_admin.email
        )
    except WorkspaceError as exc:
        raise _http(exc) from exc
    await session.commit()
    return EnvironmentOut(**_env_ref(env).model_dump(), project=_project_ref(found), apps=0)


@router.delete("/teams/{team}/projects/{project}/environments/{environment}", status_code=204)
async def api_delete_project_environment(
    team: str,
    project: str,
    environment: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> Response:
    service = WorkspaceService(session)
    tenant = await _team(team, current_admin, service)
    try:
        service.ensure_can_write(current_admin)
        found = await service.get_project(tenant.id, project)
        env = await service.get_environment(found, environment)
        await service.delete_environment(env, actor=current_admin.email)
    except WorkspaceError as exc:
        raise _http(exc) from exc
    await session.commit()
    return Response(status_code=204)


# ── Apps ──────────────────────────────────────────────────────────


@router.get("/teams/{team}/apps", response_model=list[WorkspaceAppOut])
async def api_list_team_apps(
    team: str,
    project: str | None = None,
    environment: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[WorkspaceAppOut]:
    """A team's apps, optionally narrowed to one project (and one of its environments)."""
    service = await _synced(session)
    tenant = await _team(team, current_admin, service)
    project_id = env_id = None
    try:
        if project:
            found = await service.get_project(tenant.id, project)
            project_id = found.id
            if environment:
                env_id = (await service.get_environment(found, environment)).id
        elif environment:
            raise WorkspaceError("Filtering by environment needs a project.", 422)
    except WorkspaceError as exc:
        raise _http(exc) from exc
    rows = await service.list_apps(tenant_id=tenant.id, project_id=project_id, environment_id=env_id)
    return [_app_out(row) for row in rows]


@router.post("/teams/{team}/apps/{app_id}/move", response_model=WorkspaceAppOut)
async def api_move_team_app(
    team: str,
    app_id: str,
    payload: WorkspaceAppMove,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> WorkspaceAppOut:
    service = WorkspaceService(session)
    tenant = await _team(team, current_admin, service)
    try:
        service.ensure_can_write(current_admin)
        app = await service.move_app(
            tenant.id, app_id, environment_id=payload.environment_id, actor=current_admin.email
        )
    except WorkspaceError as exc:
        raise _http(exc) from exc
    await session.commit()
    [row] = [r for r in await service.list_apps(tenant_id=tenant.id) if r.app.id == app.id]
    return _app_out(row)


@router.get("/platform/apps", response_model=list[WorkspaceAppOut])
async def api_list_platform_apps(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> list[WorkspaceAppOut]:
    """Every app on the platform with its team — the super-admin view."""
    service = await _synced(session)
    return [_app_out(row) for row in await service.list_apps(tenant_id=None)]
