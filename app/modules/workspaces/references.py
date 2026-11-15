"""Service references: env var values that point at another service's connection details.

An app's variable can hold ``${{shop-db.url}}`` instead of a copied connection string. The
reference is stored as written and filled in at every deploy from the referenced service's
current details, so a rotated password or a moved host reaches the app on its next deploy.

Only services in the app's own environment can be referenced (ADR 0019): a staging app
cannot reach production's database by naming it. Today the referenceable services are
managed databases; their fields are below.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ManagedDatabase, WorkspaceApp
from app.models.workspace import DRIVER_ENGINE, KIND_DATABASE

# ${{ service.field }} — service names follow the database naming rules.
_REF = re.compile(r"\$\{\{\s*([a-z][a-z0-9-]*)\.([a-z_]+)\s*\}\}")

DATABASE_FIELDS = ("url", "host", "port", "user", "password", "database")
REDIS_FIELDS = ("url", "host", "port", "password")


class ServiceReferenceError(Exception):
    """A reference names a service or field that isn't available to this app."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class Reference:
    service: str
    field: str

    def __str__(self) -> str:
        return f"{self.service}.{self.field}"


@dataclass(frozen=True, slots=True)
class ReferenceTarget:
    """A service an app can reference, with the fields it offers."""

    service: str
    kind: str
    engine: str
    fields: tuple[str, ...]


def find_references(value: str) -> list[Reference]:
    """The references in a value, in order, without duplicates."""
    seen: dict[tuple[str, str], Reference] = {}
    for match in _REF.finditer(value or ""):
        seen.setdefault((match[1], match[2]), Reference(match[1], match[2]))
    return list(seen.values())


def substitute(value: str, lookup: Callable[[Reference], str]) -> str:
    """Replace every reference in ``value`` with ``lookup(reference)``."""
    return _REF.sub(lambda m: lookup(Reference(m[1], m[2])), value)


class ServiceReferences:
    """Which services an app can reference, and their current values."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _environment_id(self, tenant_id: str, stack: str) -> str | None:
        row = await self._app_row(tenant_id, stack)
        if row is None:
            # A brand-new stack may not be indexed yet; sync places it.
            from app.modules.workspaces.service import WorkspaceService

            await WorkspaceService(self.session).sync()
            row = await self._app_row(tenant_id, stack)
        return row.environment_id if row is not None else None

    async def _app_row(self, tenant_id: str, stack: str) -> WorkspaceApp | None:
        return await self.session.scalar(
            select(WorkspaceApp).where(
                WorkspaceApp.tenant_id == tenant_id,
                WorkspaceApp.driver == DRIVER_ENGINE,
                WorkspaceApp.external_id == stack,
            )
        )

    async def _databases(self, tenant_id: str, stack: str) -> dict[str, ManagedDatabase]:
        """The managed databases in the same environment as ``stack``, by service name."""
        env_id = await self._environment_id(tenant_id, stack)
        if env_id is None:
            return {}
        rows = await self.session.scalars(
            select(WorkspaceApp).where(
                WorkspaceApp.tenant_id == tenant_id,
                WorkspaceApp.environment_id == env_id,
                WorkspaceApp.kind == KIND_DATABASE,
            )
        )
        stacks = [row.external_id for row in rows.all()]
        if not stacks:
            return {}
        dbs = await self.session.scalars(
            select(ManagedDatabase).where(
                ManagedDatabase.tenant_id == tenant_id, ManagedDatabase.project.in_(stacks)
            )
        )
        return {db.name: db for db in dbs.all()}

    @staticmethod
    def _fields(db: ManagedDatabase) -> tuple[str, ...]:
        return REDIS_FIELDS if db.engine == "redis" else DATABASE_FIELDS

    async def available(self, tenant_id: str | None, stack: str) -> list[ReferenceTarget]:
        dbs = await self._databases(tenant_id or "", stack)
        return [
            ReferenceTarget(service=name, kind=KIND_DATABASE, engine=db.engine, fields=self._fields(db))
            for name, db in sorted(dbs.items())
        ]

    async def check(self, tenant_id: str | None, stack: str, value: str) -> list[Reference]:
        """Raise ServiceReferenceError unless every reference in ``value`` resolves for ``stack``."""
        refs = find_references(value)
        if not refs:
            return refs
        dbs = await self._databases(tenant_id or "", stack)
        for ref in refs:
            self._target(dbs, ref)
        return refs

    def _target(self, dbs: dict[str, ManagedDatabase], ref: Reference) -> ManagedDatabase:
        db = dbs.get(ref.service)
        if db is None:
            raise ServiceReferenceError(
                f"${{{{{ref}}}}}: there is no service named '{ref.service}' in this app's "
                "environment."
            )
        if ref.field not in self._fields(db):
            raise ServiceReferenceError(
                f"${{{{{ref}}}}}: '{ref.service}' has no field '{ref.field}' "
                f"(use one of: {', '.join(self._fields(db))})."
            )
        return db

    async def resolve(
        self, tenant_id: str | None, stack: str, env: dict[str, str]
    ) -> dict[str, str]:
        """``env`` with every reference filled in; ServiceReferenceError if one doesn't resolve."""
        if not any(find_references(v) for v in env.values()):
            return env
        from app.modules.databases.service import DatabasesService

        dbs = await self._databases(tenant_id or "", stack)
        service = DatabasesService()
        details: dict[str, dict[str, str | int]] = {}

        def lookup(ref: Reference) -> str:
            db = self._target(dbs, ref)
            if db.name not in details:
                try:
                    details[db.name] = service.connection(db)
                except Exception as exc:  # noqa: BLE001 — surfaced as a reference failure
                    raise ServiceReferenceError(
                        f"${{{{{ref}}}}}: {getattr(exc, 'message', None) or exc}"
                    ) from exc
            return str(details[db.name][ref.field])

        return {key: substitute(value, lookup) for key, value in env.items()}
