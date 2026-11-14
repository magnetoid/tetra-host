"""`/api/v1/databases/...` — managed databases and their backups.

Own router (roadmap phase 1: new capabilities do not grow ``app/api/routes.py``). Every route
is tenant-scoped through ``DatabasesService``; another tenant's database answers 404.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import get_current_api_admin
from app.db.session import get_db_session
from app.models import AdminUser
from app.models.database import DatabaseBackup
from app.modules.databases.service import DatabasesService, DatabaseView
from app.services.db_engines import ENGINES
from app.services.docker_engine import DockerEngineError

router = APIRouter(prefix="/api/v1", tags=["api"])


# ── Contracts ─────────────────────────────────────────────────────


class DatabaseEngineOut(BaseModel):
    key: str
    label: str
    versions: list[str]
    default_version: str
    supports_backup: bool


class DatabaseOut(BaseModel):
    id: str
    name: str
    engine: str
    engine_label: str
    version: str
    status: str
    host: str
    port: int
    supports_backup: bool
    backup_cron: str
    backup_keep: int
    created_at: datetime


class DatabaseCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=32)
    engine: str
    version: str | None = None
    environment_id: str | None = None


class DatabaseUpdateRequest(BaseModel):
    backup_cron: str | None = None
    backup_keep: int | None = None


class DatabaseConnectionOut(BaseModel):
    host: str
    port: int
    user: str
    database: str
    password: str
    url: str


class DatabaseLinkRequest(BaseModel):
    project: str
    key: str = "DATABASE_URL"


class DatabaseBackupOut(BaseModel):
    id: str
    status: str
    trigger: str
    size_bytes: int
    error: str
    restore_status: str
    restore_error: str
    restored_at: datetime | None
    created_at: datetime
    finished_at: datetime | None


class DatabaseActionOut(BaseModel):
    ok: bool = True
    message: str


def _utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; they are UTC, so say so on the wire."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _http(exc: DockerEngineError) -> HTTPException:
    return HTTPException(status_code=int(exc.code or status.HTTP_502_BAD_GATEWAY), detail=str(exc))


def _out(view: DatabaseView) -> DatabaseOut:
    db, spec = view.db, view.spec
    return DatabaseOut(
        id=db.id, name=db.name, engine=db.engine, engine_label=spec.label, version=db.version,
        status=view.status, host=db.name, port=spec.port, supports_backup=spec.supports_backup,
        backup_cron=db.backup_cron, backup_keep=db.backup_keep, created_at=_utc(db.created_at),
    )


def _backup_out(b: DatabaseBackup) -> DatabaseBackupOut:
    return DatabaseBackupOut(
        id=b.id, status=b.status, trigger=b.trigger, size_bytes=b.size_bytes, error=b.error,
        restore_status=b.restore_status, restore_error=b.restore_error,
        restored_at=_utc(b.restored_at), created_at=_utc(b.created_at),
        finished_at=_utc(b.finished_at),
    )


# ── Routes ────────────────────────────────────────────────────────


@router.get("/databases/engines", response_model=list[DatabaseEngineOut])
async def api_database_engines(
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DatabaseEngineOut]:
    return [
        DatabaseEngineOut(
            key=s.key, label=s.label, versions=list(s.versions),
            default_version=s.default_version, supports_backup=s.supports_backup,
        )
        for s in ENGINES.values()
    ]


@router.get("/databases", response_model=list[DatabaseOut])
async def api_databases_list(
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DatabaseOut]:
    views = await DatabasesService().list_for_tenant(session, current_admin.tenant_id)
    return [_out(v) for v in views]


@router.post("/databases", response_model=DatabaseOut, status_code=status.HTTP_201_CREATED)
async def api_databases_create(
    payload: DatabaseCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseOut:
    service = DatabasesService()
    try:
        db = await service.create_for_tenant(
            session, current_admin.tenant_id,
            name=payload.name, engine=payload.engine, version=payload.version,
            environment_id=payload.environment_id,
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return _out(DatabaseView(db=db, status="starting", spec=service.spec_for(db)))


@router.get("/databases/{database_id}", response_model=DatabaseOut)
async def api_databases_get(
    database_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseOut:
    try:
        view = await DatabasesService().view_for_tenant(
            session, current_admin.tenant_id, database_id
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return _out(view)


@router.patch("/databases/{database_id}", response_model=DatabaseOut)
async def api_databases_update(
    database_id: str,
    payload: DatabaseUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseOut:
    service = DatabasesService()
    try:
        await service.update_backup_schedule(
            session, current_admin.tenant_id, database_id,
            cron=payload.backup_cron, keep=payload.backup_keep,
        )
        view = await service.view_for_tenant(session, current_admin.tenant_id, database_id)
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return _out(view)


@router.delete("/databases/{database_id}", response_model=DatabaseActionOut)
async def api_databases_delete(
    database_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseActionOut:
    try:
        await DatabasesService().delete_for_tenant(session, current_admin.tenant_id, database_id)
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return DatabaseActionOut(message="Database, data and backups removed.")


@router.get("/databases/{database_id}/connection", response_model=DatabaseConnectionOut)
async def api_databases_connection(
    database_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseConnectionOut:
    """Credentials and URL for apps on the tenant network (the host is the database name)."""
    service = DatabasesService()
    try:
        db = await service.get_for_tenant(session, current_admin.tenant_id, database_id)
        return DatabaseConnectionOut(**service.connection(db))
    except DockerEngineError as exc:
        raise _http(exc) from exc


@router.post("/databases/{database_id}/link", response_model=DatabaseActionOut)
async def api_databases_link(
    database_id: str,
    payload: DatabaseLinkRequest,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseActionOut:
    try:
        await DatabasesService().link_for_tenant(
            session, current_admin.tenant_id, database_id,
            project=payload.project, key=payload.key,
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return DatabaseActionOut(
        message=f"{payload.key} set on {payload.project}. Redeploy the app to use it."
    )


@router.get("/databases/{database_id}/backups", response_model=list[DatabaseBackupOut])
async def api_database_backups(
    database_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> list[DatabaseBackupOut]:
    try:
        backups = await DatabasesService().list_backups_for_tenant(
            session, current_admin.tenant_id, database_id
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return [_backup_out(b) for b in backups]


@router.post(
    "/databases/{database_id}/backups",
    response_model=DatabaseBackupOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def api_database_backup_start(
    database_id: str,
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseBackupOut:
    try:
        backup = await DatabasesService().start_backup(current_admin.tenant_id, database_id)
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return _backup_out(backup)


@router.post(
    "/databases/{database_id}/backups/{backup_id}/restore",
    response_model=DatabaseBackupOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def api_database_backup_restore(
    database_id: str,
    backup_id: str,
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseBackupOut:
    """Replace the database's current contents with this backup."""
    try:
        backup = await DatabasesService().start_restore(
            current_admin.tenant_id, database_id, backup_id
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return _backup_out(backup)


@router.delete("/databases/{database_id}/backups/{backup_id}", response_model=DatabaseActionOut)
async def api_database_backup_delete(
    database_id: str,
    backup_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseActionOut:
    try:
        await DatabasesService().delete_backup_for_tenant(
            session, current_admin.tenant_id, database_id, backup_id
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    return DatabaseActionOut(message="Backup deleted.")


# Last: the {action} segment would otherwise shadow /link and /backups.
@router.post("/databases/{database_id}/{action}", response_model=DatabaseActionOut)
async def api_databases_control(
    database_id: str,
    action: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(get_current_api_admin),
) -> DatabaseActionOut:
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        await DatabasesService().control_for_tenant(
            session, current_admin.tenant_id, database_id, action
        )
    except DockerEngineError as exc:
        raise _http(exc) from exc
    past = {"start": "started", "stop": "stopped", "restart": "restarted"}[action]
    return DatabaseActionOut(message=f"Database {past}.")
