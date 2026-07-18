"""Databases service — tenant-scoped wrappers around the Coolify databases API."""

import logging
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import TenantResource
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_DATABASE
from app.services.coolify import CoolifyClient, CoolifyDatabase, DB_TYPE_ALLOWLIST
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter

logger = logging.getLogger(__name__)


class DatabasesService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CoolifyClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        self.actions_enabled = get_settings().enable_provider_actions

    def _require_actions(self) -> None:
        if not self.actions_enabled:
            raise ProviderAPIError(
                service="Coolify",
                message="Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false).",
                status_code=403,
            )

    async def list_targets(self) -> dict[str, list[dict[str, str]]]:
        """Coolify servers + projects to populate the provisioning form's pickers.

        Best-effort: returns empty lists if Coolify isn't configured or a call fails, so the
        console can still render (the form just shows no options)."""
        servers: list[dict[str, str]] = []
        projects: list[dict[str, str]] = []
        try:
            for s in await self.client.list_servers():
                if s.is_usable:
                    servers.append({"uuid": s.id, "name": s.name})
        except ProviderAPIError:
            logger.warning("could not list Coolify servers for the provisioning form")
        try:
            for p in await self.client.list_projects():
                uuid = str(p.get("uuid") or p.get("id") or "")
                if uuid:
                    projects.append({"uuid": uuid, "name": str(p.get("name") or uuid)})
        except ProviderAPIError:
            logger.warning("could not list Coolify projects for the provisioning form")
        return {"servers": servers, "projects": projects}

    async def _ensure_database_access(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        db_uuid: str,
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_COOLIFY,
            resource_type=RESOURCE_TYPE_DATABASE,
            external_id=db_uuid,
        )
        if not allowed:
            raise ProviderAPIError(
                service="Coolify",
                message="Database is not assigned to this tenant.",
                status_code=403,
            )

    async def list_databases(self, refresh: bool = False) -> list[CoolifyDatabase]:
        return await self.client.list_databases()

    async def list_databases_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        refresh: bool = False,
    ) -> list[CoolifyDatabase]:
        databases = await self.list_databases(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_databases(databases)

    async def provision_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        db_type: str,
        name: str,
        server_uuid: str,
        project_uuid: str,
        environment_name: str,
    ) -> dict[str, Any]:
        """Provision a new managed database via Coolify and record it as a TenantResource.

        Steps:
        1. Guard: tenant_id must be non-empty (raises ProviderAPIError 400 otherwise).
        2. Gate on ENABLE_PROVIDER_ACTIONS (raises ProviderAPIError 403 if disabled).
        3. Validate db_type against DB_TYPE_ALLOWLIST (raises ValueError if invalid — caller maps to 422).
        4. Call Coolify: POST /api/v1/databases/{db_type}.
        5. On success, create TenantResource(provider=coolify, resource_type=database, external_id=<uuid>).
           Raises ProviderAPIError(502) if Coolify returns no uuid/id — never a silent orphan.
        6. On Coolify failure, ProviderAPIError propagates (no TenantResource created).
        """
        # Fix 2: reject empty tenant_id before touching Coolify.
        if not tenant_id:
            raise ProviderAPIError(
                service="Coolify",
                message="Cannot provision a database without a tenant.",
                status_code=400,
            )

        self._require_actions()

        if db_type not in DB_TYPE_ALLOWLIST:
            raise ValueError(
                f"Unsupported db_type '{db_type}'. "
                f"Supported types: {', '.join(sorted(DB_TYPE_ALLOWLIST))}"
            )

        logger.info("provisioning %s database '%s' for tenant %s", db_type, name, tenant_id)
        result = await self.client.provision_database(
            db_type=db_type,
            server_uuid=server_uuid,
            project_uuid=project_uuid,
            environment_name=environment_name,
            name=name,
        )

        # Extract the new database's UUID from the Coolify response.
        # Coolify v4 returns {"uuid": "...", "name": "..."} on creation.
        db_uuid = str(result.get("uuid") or result.get("id") or "")

        # Fix 1: fail loud when Coolify returns no uuid — never create a silent orphan.
        if not db_uuid:
            logger.error("Coolify returned no UUID after provisioning database '%s'", name)
            raise ProviderAPIError(
                service="Coolify",
                message="Provision succeeded but Coolify returned no database UUID.",
                status_code=502,
            )

        resource = TenantResource(
            tenant_id=tenant_id,
            provider=PROVIDER_COOLIFY,
            resource_type=RESOURCE_TYPE_DATABASE,
            external_id=db_uuid,
            display_name=name,
        )
        session.add(resource)
        await session.flush()

        logger.info("database '%s' provisioned (uuid %s, tenant %s)", name, db_uuid, tenant_id)
        result.setdefault("ok", True)
        return result

    async def backups_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        db_uuid: str,
    ) -> list[dict[str, Any]]:
        """List backup configs for a tenant-owned database."""
        await self._ensure_database_access(session, tenant_id, db_uuid)
        return await self.client.list_database_backups(db_uuid)

    async def create_backup_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        db_uuid: str,
        **config: Any,
    ) -> dict[str, Any]:
        """Create a backup config for a tenant-owned database."""
        self._require_actions()
        await self._ensure_database_access(session, tenant_id, db_uuid)
        return await self.client.create_database_backup(db_uuid, **config)
