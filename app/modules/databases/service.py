"""Managed databases — create, control, connect, back up and restore a tenant's databases.

A database is one compose stack on the Tetra Engine (``app/services/db_engines.py`` renders it)
on the tenant's private network (``app/services/tenant_network.py``). Backups are gzipped SQL
dumps streamed out of the container to ``DATABASE_BACKUP_DIR``; restores stream one back in.
Backups and restores run as background tasks and record their outcome on the backup row.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_scope
from app.models import Tenant, TenantResource
from app.models.database import (
    BACKUP_ERROR,
    BACKUP_OK,
    BACKUP_RUNNING,
    TRIGGER_MANUAL,
    TRIGGER_SCHEDULED,
    DatabaseBackup,
    ManagedDatabase,
)
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.services import db_engines
from app.services.cron import cron_matches, is_valid_cron
from app.services.db_engines import ENGINES, EngineSpec, InvalidDatabaseSpec
from app.services.docker_engine import DockerEngine, DockerEngineError
from app.services.quota import QuotaService
from app.services.secrets import decrypt, encrypt
from app.services.tenant_network import tenant_network_name

logger = logging.getLogger(__name__)

# Strong references to running backup/restore tasks (asyncio keeps only weak ones).
_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _now() -> datetime:
    return datetime.now(UTC)


def _backup_root() -> Path:
    root = Path(get_settings().database_backup_dir)
    return root if root.is_absolute() else Path.cwd() / root


def _database_dir(db: ManagedDatabase) -> Path:
    return _backup_root() / (db.tenant_id or "platform") / db.id


@dataclass(slots=True)
class DatabaseView:
    db: ManagedDatabase
    status: str
    spec: EngineSpec


async def tenant_has_databases(session: AsyncSession, tenant_id: str | None) -> bool:
    count = await session.scalar(
        select(func.count())
        .select_from(ManagedDatabase)
        .where(ManagedDatabase.tenant_id == (tenant_id or ""))
    )
    return bool(count)


class DatabasesService:
    def __init__(self, engine: DockerEngine | None = None) -> None:
        settings = get_settings()
        self.engine = engine or DockerEngine(docker_bin=settings.docker_bin)
        self.actions_enabled = settings.enable_provider_actions

    # ── helpers ───────────────────────────────────────────────────────

    def _require_actions(self) -> None:
        if not self.actions_enabled:
            raise DockerEngineError(
                message="Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false).", code=403
            )

    @staticmethod
    def spec_for(db: ManagedDatabase) -> EngineSpec:
        return ENGINES[db.engine]

    @staticmethod
    def credentials(db: ManagedDatabase) -> dict[str, str]:
        try:
            return json.loads(decrypt(db.secret) or "{}")
        except json.JSONDecodeError:
            return {}

    def connection(self, db: ManagedDatabase) -> dict[str, str | int]:
        spec = self.spec_for(db)
        creds = self.credentials(db)
        if not creds.get("password"):
            raise DockerEngineError(
                message="The stored credentials can't be read (was APP_SECRET rotated?).",
                code=409,
            )
        return {
            "host": db.name,
            "port": spec.port,
            "user": creds.get("user", ""),
            "database": creds.get("database", ""),
            "password": creds["password"],
            "url": db_engines.connection_url(spec, host=db.name, creds=creds),
        }

    async def get_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, database_id: str
    ) -> ManagedDatabase:
        db = await session.get(ManagedDatabase, database_id)
        if db is None or db.tenant_id != (tenant_id or ""):
            raise DockerEngineError(message="Database not found.", code=404)
        return db

    async def _status_map(self) -> dict[str, str]:
        try:
            stacks = await self.engine.list_stacks()
        except DockerEngineError:
            return {}
        return {
            str(s.get("Name") or ""): str(s.get("Status") or "")
            for s in stacks
            if s.get("Name")
        }

    async def _check_quota(self, session: AsyncSession, tenant_id: str) -> None:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is not None and tenant.is_platform_scope:
            return
        limit = get_settings().max_databases_per_tenant
        count = await session.scalar(
            select(func.count())
            .select_from(ManagedDatabase)
            .where(ManagedDatabase.tenant_id == tenant_id)
        )
        if (count or 0) >= limit:
            raise DockerEngineError(
                message=f"Database limit reached ({limit}). Remove one before creating another.",
                code=402,
            )

    # ── lifecycle ─────────────────────────────────────────────────────

    async def list_for_tenant(
        self, session: AsyncSession, tenant_id: str | None
    ) -> list[DatabaseView]:
        rows = list(
            (
                await session.scalars(
                    select(ManagedDatabase)
                    .where(ManagedDatabase.tenant_id == (tenant_id or ""))
                    .order_by(ManagedDatabase.name)
                )
            ).all()
        )
        status = await self._status_map() if rows else {}
        return [
            DatabaseView(db=row, status=status.get(row.project, "unknown"), spec=self.spec_for(row))
            for row in rows
        ]

    async def view_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, database_id: str
    ) -> DatabaseView:
        db = await self.get_for_tenant(session, tenant_id, database_id)
        status = await self._status_map()
        return DatabaseView(db=db, status=status.get(db.project, "unknown"), spec=self.spec_for(db))

    async def create_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        name: str,
        engine: str,
        version: str | None = None,
    ) -> ManagedDatabase:
        self._require_actions()
        try:
            name = db_engines.validate_name(name)
            spec, version = db_engines.resolve_engine(engine, version)
        except InvalidDatabaseSpec as exc:
            raise DockerEngineError(message=str(exc), code=422) from exc
        tenant = tenant_id or ""
        taken = await session.scalar(
            select(ManagedDatabase).where(
                ManagedDatabase.tenant_id == tenant, ManagedDatabase.name == name
            )
        )
        if taken is not None:
            raise DockerEngineError(message=f"A database named '{name}' already exists.", code=409)
        await self._check_quota(session, tenant)

        creds = db_engines.new_credentials(spec, name)
        database_id = str(uuid4())
        db = ManagedDatabase(
            id=database_id, tenant_id=tenant, name=name, engine=spec.key, version=version,
            # Compose project names are global on the host, so key them by id, not name.
            project=f"tdb-{database_id.replace('-', '')[:12]}",
            secret=encrypt(json.dumps(creds)),
            backup_cron="0 3 * * *" if spec.supports_backup else "",
        )
        session.add(db)
        await session.flush()

        allocation = await QuotaService(session, tenant).plan_allocation()
        network = tenant_network_name(tenant)
        compose = db_engines.compose_for_database(
            spec, version, name=name, creds=creds, network=network,
            cpu_millicores=allocation.cpu_millicores, mem_mb=allocation.mem_mb,
        )
        logger.info("creating %s database '%s' (tenant %s)", spec.key, name, tenant)
        try:
            await self.engine.ensure_network(network, labels={"tetra.tenant": tenant or "platform"})
            await self.engine.deploy_stack(db.project, compose, {})
        except Exception:
            logger.exception("database '%s' failed to start; removing it", name)
            try:
                await self.engine.remove_stack(db.project, volumes=True)
            except DockerEngineError:
                pass
            raise
        return db

    async def control_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, database_id: str, action: str
    ) -> ManagedDatabase:
        self._require_actions()
        db = await self.get_for_tenant(session, tenant_id, database_id)
        if action == "start":
            await self.engine.start_stack(db.project)
        elif action == "stop":
            await self.engine.stop_stack(db.project)
        elif action == "restart":
            await self.engine.restart_stack(db.project)
        else:
            raise DockerEngineError(message=f"Unknown action '{action}'.", code=400)
        return db

    async def delete_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, database_id: str
    ) -> None:
        """Remove the database, its data volume and all of its backups."""
        self._require_actions()
        db = await self.get_for_tenant(session, tenant_id, database_id)
        if await self._busy(session, db.id):
            raise DockerEngineError(
                message="A backup or restore is running; try again when it finishes.", code=409
            )
        logger.info("removing database '%s' (tenant %s)", db.name, db.tenant_id)
        await self.engine.remove_stack(db.project, volumes=True)
        shutil.rmtree(_database_dir(db), ignore_errors=True)
        await session.execute(delete(DatabaseBackup).where(DatabaseBackup.database_id == db.id))
        await session.delete(db)

    async def link_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        database_id: str,
        *,
        project: str,
        key: str = "DATABASE_URL",
    ) -> None:
        """Store the connection URL as a secret env var on one of the tenant's apps."""
        from app.modules.deploys.service import DeploysService

        db = await self.get_for_tenant(session, tenant_id, database_id)
        key = (key or "").strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise DockerEngineError(message="Env var name must be letters, digits and _.", code=422)
        owned = await session.scalar(
            select(TenantResource).where(
                TenantResource.tenant_id == (tenant_id or ""),
                TenantResource.provider == PROVIDER_DOCKER,
                TenantResource.resource_type == RESOURCE_TYPE_APP,
                TenantResource.external_id == project,
            )
        )
        if owned is None:
            raise DockerEngineError(message="App is not assigned to this tenant.", code=403)
        url = str(self.connection(db)["url"])
        await DeploysService(None).set_env_for_tenant(
            session, tenant_id, project, key=key, value=url, is_secret=True
        )

    async def update_backup_schedule(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        database_id: str,
        *,
        cron: str | None = None,
        keep: int | None = None,
    ) -> ManagedDatabase:
        db = await self.get_for_tenant(session, tenant_id, database_id)
        if cron is not None:
            cron = cron.strip()
            if cron and not self.spec_for(db).supports_backup:
                raise DockerEngineError(
                    message=f"{self.spec_for(db).label} backups are not supported yet.", code=422
                )
            if cron and not is_valid_cron(cron):
                raise DockerEngineError(message=f"'{cron}' is not a valid cron expression.", code=422)
            db.backup_cron = cron
        if keep is not None:
            if not 1 <= keep <= 90:
                raise DockerEngineError(message="Keep between 1 and 90 backups.", code=422)
            db.backup_keep = keep
        return db

    # ── backups ───────────────────────────────────────────────────────

    @staticmethod
    async def _busy(session: AsyncSession, database_id: str) -> bool:
        running = await session.scalar(
            select(func.count())
            .select_from(DatabaseBackup)
            .where(
                DatabaseBackup.database_id == database_id,
                (DatabaseBackup.status == BACKUP_RUNNING)
                | (DatabaseBackup.restore_status == BACKUP_RUNNING),
            )
        )
        return bool(running)

    async def list_backups_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, database_id: str
    ) -> list[DatabaseBackup]:
        db = await self.get_for_tenant(session, tenant_id, database_id)
        return list(
            (
                await session.scalars(
                    select(DatabaseBackup)
                    .where(DatabaseBackup.database_id == db.id)
                    .order_by(DatabaseBackup.created_at.desc())
                )
            ).all()
        )

    async def start_backup(
        self, tenant_id: str | None, database_id: str, *, trigger: str = TRIGGER_MANUAL
    ) -> DatabaseBackup:
        """Record a running backup and start the dump in the background."""
        self._require_actions()
        async with session_scope() as session:
            db = await self.get_for_tenant(session, tenant_id, database_id)
            if not self.spec_for(db).supports_backup:
                raise DockerEngineError(
                    message=f"{self.spec_for(db).label} backups are not supported yet.", code=422
                )
            if await self._busy(session, db.id):
                raise DockerEngineError(
                    message="A backup or restore is already running for this database.", code=409
                )
            backup = DatabaseBackup(database_id=db.id, tenant_id=db.tenant_id, trigger=trigger)
            session.add(backup)
            await session.flush()
            stamp = _now().strftime("%Y%m%dT%H%M%SZ")
            backup.filename = f"{db.tenant_id or 'platform'}/{db.id}/{stamp}-{backup.id[:8]}.sql.gz"
        _spawn(self._run_backup(backup.id))
        return backup

    async def _run_backup(self, backup_id: str) -> None:
        async with session_scope() as session:
            backup = await session.get(DatabaseBackup, backup_id)
            db = await session.get(ManagedDatabase, backup.database_id) if backup else None
            if backup is None or db is None:
                return
            project, spec = db.project, self.spec_for(db)
            path = _backup_root() / backup.filename
        status, error, size = BACKUP_OK, "", 0
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            await self.engine.exec_to_gzip(
                project, db_engines.SERVICE, db_engines.dump_script(spec), str(path)
            )
            size = path.stat().st_size
            logger.info("backup %s written (%d bytes)", backup_id, size)
        except asyncio.CancelledError:
            path.unlink(missing_ok=True)
            status, error = BACKUP_ERROR, "Interrupted (the panel restarted)."
            await self._finish_backup(backup_id, status, error, size)
            raise
        except Exception as exc:  # noqa: BLE001 — record every failure on the row
            logger.warning("backup %s failed: %s", backup_id, exc)
            path.unlink(missing_ok=True)
            status, error = BACKUP_ERROR, str(exc)[:500]
        await self._finish_backup(backup_id, status, error, size)
        if status == BACKUP_OK:
            await self._prune(backup_id)

    async def _finish_backup(self, backup_id: str, status: str, error: str, size: int) -> None:
        async with session_scope() as session:
            backup = await session.get(DatabaseBackup, backup_id)
            if backup is not None:
                backup.status, backup.error, backup.size_bytes = status, error, size
                backup.finished_at = _now()

    async def _prune(self, backup_id: str) -> None:
        """Keep the newest ``backup_keep`` scheduled backups; manual ones are left alone."""
        async with session_scope() as session:
            backup = await session.get(DatabaseBackup, backup_id)
            db = await session.get(ManagedDatabase, backup.database_id) if backup else None
            if db is None:
                return
            scheduled = list(
                (
                    await session.scalars(
                        select(DatabaseBackup)
                        .where(
                            DatabaseBackup.database_id == db.id,
                            DatabaseBackup.trigger == TRIGGER_SCHEDULED,
                            DatabaseBackup.status == BACKUP_OK,
                        )
                        .order_by(DatabaseBackup.created_at.desc())
                    )
                ).all()
            )
            for old in scheduled[db.backup_keep:]:
                (_backup_root() / old.filename).unlink(missing_ok=True)
                await session.delete(old)

    async def delete_backup_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, database_id: str, backup_id: str
    ) -> None:
        backup = await self._backup(session, tenant_id, database_id, backup_id)
        if BACKUP_RUNNING in (backup.status, backup.restore_status):
            raise DockerEngineError(message="This backup is in use; try again shortly.", code=409)
        if backup.filename:
            (_backup_root() / backup.filename).unlink(missing_ok=True)
        await session.delete(backup)

    async def _backup(
        self, session: AsyncSession, tenant_id: str | None, database_id: str, backup_id: str
    ) -> DatabaseBackup:
        db = await self.get_for_tenant(session, tenant_id, database_id)
        backup = await session.get(DatabaseBackup, backup_id)
        if backup is None or backup.database_id != db.id:
            raise DockerEngineError(message="Backup not found.", code=404)
        return backup

    async def start_restore(
        self, tenant_id: str | None, database_id: str, backup_id: str
    ) -> DatabaseBackup:
        """Replace the database's contents with a backup, in the background."""
        self._require_actions()
        async with session_scope() as session:
            backup = await self._backup(session, tenant_id, database_id, backup_id)
            if backup.status != BACKUP_OK:
                raise DockerEngineError(message="Only a finished backup can be restored.", code=409)
            if not (_backup_root() / backup.filename).is_file():
                raise DockerEngineError(message="The backup file is missing on the host.", code=410)
            if await self._busy(session, database_id):
                raise DockerEngineError(
                    message="A backup or restore is already running for this database.", code=409
                )
            backup.restore_status, backup.restore_error = BACKUP_RUNNING, ""
        _spawn(self._run_restore(backup_id))
        return backup

    async def _run_restore(self, backup_id: str) -> None:
        async with session_scope() as session:
            backup = await session.get(DatabaseBackup, backup_id)
            db = await session.get(ManagedDatabase, backup.database_id) if backup else None
            if backup is None or db is None:
                return
            project, spec = db.project, self.spec_for(db)
            path = _backup_root() / backup.filename
        status, error = BACKUP_OK, ""
        try:
            await self.engine.exec_from_gzip(
                project, db_engines.SERVICE, db_engines.restore_script(spec), str(path)
            )
            logger.info("restore from backup %s finished", backup_id)
        except asyncio.CancelledError:
            status, error = BACKUP_ERROR, "Interrupted (the panel restarted); check the data."
            await self._finish_restore(backup_id, status, error)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("restore from backup %s failed: %s", backup_id, exc)
            status, error = BACKUP_ERROR, str(exc)[:500]
        await self._finish_restore(backup_id, status, error)

    async def _finish_restore(self, backup_id: str, status: str, error: str) -> None:
        async with session_scope() as session:
            backup = await session.get(DatabaseBackup, backup_id)
            if backup is not None:
                backup.restore_status, backup.restore_error = status, error
                backup.restored_at = _now()


async def run_scheduled_backups(now: datetime) -> int:
    """Start a backup for every database whose schedule matches ``now``. Returns how many."""
    async with session_scope() as session:
        due = [
            (db.tenant_id, db.id)
            for db in (await session.scalars(select(ManagedDatabase))).all()
            if db.backup_cron and ENGINES[db.engine].supports_backup
            and cron_matches(db.backup_cron, now)
        ]
    service = DatabasesService()
    started = 0
    for tenant_id, database_id in due:
        try:
            await service.start_backup(tenant_id, database_id, trigger=TRIGGER_SCHEDULED)
            started += 1
        except DockerEngineError as exc:
            logger.warning("scheduled backup of database %s skipped: %s", database_id, exc)
    return started


async def mark_interrupted_operations() -> None:
    """On startup, close backups and restores a previous process left running."""
    async with session_scope() as session:
        for backup in (
            await session.scalars(
                select(DatabaseBackup).where(
                    (DatabaseBackup.status == BACKUP_RUNNING)
                    | (DatabaseBackup.restore_status == BACKUP_RUNNING)
                )
            )
        ).all():
            if backup.status == BACKUP_RUNNING:
                backup.status, backup.error = BACKUP_ERROR, "Interrupted (the panel restarted)."
                backup.finished_at = _now()
            if backup.restore_status == BACKUP_RUNNING:
                backup.restore_status = BACKUP_ERROR
                backup.restore_error = "Interrupted (the panel restarted); check the data."
