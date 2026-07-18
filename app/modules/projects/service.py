import logging
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.services.coolify import (
    CoolifyApplication,
    CoolifyClient,
    CoolifyDeployment,
    CoolifyScheduledTask,
    CoolifyStorage,
)
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter

logger = logging.getLogger(__name__)


class ProjectsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CoolifyClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )

    async def _ensure_tenant_access(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_COOLIFY,
            resource_type=RESOURCE_TYPE_SITE,
            external_id=application_id,
        )
        if not allowed:
            raise ProviderAPIError(service="Coolify", message="Application is not assigned to this tenant.", status_code=403)

    async def ensure_access_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> None:
        """Public tenant-access guard.

        Used by streaming endpoints that must validate access once up front
        (the request DB session is not safely usable inside a long-lived
        StreamingResponse generator).
        """
        await self._ensure_tenant_access(session, tenant_id, application_id)

    async def list_sites(self, refresh: bool = False) -> list[CoolifyApplication]:
        return await self.client.list_applications(refresh=refresh)

    async def list_sites_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        refresh: bool = False,
    ) -> list[CoolifyApplication]:
        sites = await self.list_sites(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_sites(sites)

    # ── Actions ───────────────────────────────────────────────────

    async def deploy_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, force: bool = False, tag: str = "",
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.deploy_application(application_id, force=force, tag=tag)

    async def start_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        logger.info("starting application %s (tenant %s)", application_id, tenant_id)
        return await self.client.start_application(application_id)

    async def restart_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        logger.info("restarting application %s (tenant %s)", application_id, tenant_id)
        return await self.client.restart_application(application_id)

    async def stop_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        logger.info("stopping application %s (tenant %s)", application_id, tenant_id)
        return await self.client.stop_application(application_id)

    # ── Detail & Raw ──────────────────────────────────────────────

    async def get_site_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> CoolifyApplication | None:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.get_application(application_id)

    async def get_site_raw_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> dict[str, Any]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.get_application_raw(application_id)

    async def update_site_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, data: dict[str, Any],
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.update_application(application_id, data)

    async def delete_site_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.delete_application(application_id)

    # ── Logs & Execute ────────────────────────────────────────────

    async def get_logs_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, lines: int = 100,
    ) -> str:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.get_application_logs(application_id, lines=lines)

    async def execute_command_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, command: str,
    ) -> str:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        # The command itself is intentionally not logged (may embed secrets).
        logger.info("executing command in application %s (tenant %s)", application_id, tenant_id)
        return await self.client.execute_command(application_id, command)

    # ── Environment Variables ─────────────────────────────────────

    async def get_envs_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> list:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.get_application_envs(application_id)

    async def create_env_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, key: str, value: str,
        is_preview: bool = False, is_build_time: bool = False,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.create_env(application_id, key, value, is_preview, is_build_time)

    async def update_env_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, key: str, value: str,
        is_preview: bool = False, is_build_time: bool = False,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.update_env(application_id, key, value, is_preview, is_build_time)

    async def delete_env_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, env_uuid: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.delete_env(application_id, env_uuid)

    # ── Deployments ───────────────────────────────────────────────

    async def list_deployments_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> list[CoolifyDeployment]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.list_deployments_for_application(application_id)

    async def get_deployment_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, deployment_uuid: str,
    ) -> CoolifyDeployment | None:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.get_deployment(deployment_uuid)

    async def cancel_deployment_for_tenant(
        self, session: AsyncSession, tenant_id: str | None,
        application_id: str, deployment_uuid: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.cancel_deployment(deployment_uuid)


    async def list_scheduled_tasks_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> list[CoolifyScheduledTask]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.list_scheduled_tasks(application_id)

    async def create_scheduled_task_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, data: dict[str, Any],
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.create_scheduled_task(application_id, data)

    async def update_scheduled_task_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, task_uuid: str, data: dict[str, Any],
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.update_scheduled_task(application_id, task_uuid, data)

    async def delete_scheduled_task_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, task_uuid: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.delete_scheduled_task(application_id, task_uuid)

    async def list_scheduled_task_executions_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, task_uuid: str,
    ) -> list[dict[str, Any]]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.list_scheduled_task_executions(application_id, task_uuid)

    async def list_storages_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str,
    ) -> list[CoolifyStorage]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.list_storages(application_id)

    async def create_storage_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, data: dict[str, Any],
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.create_storage(application_id, data)

    async def update_storage_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, data: dict[str, Any],
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.update_storage(application_id, data)

    async def delete_storage_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, application_id: str, storage_uuid: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.delete_storage(application_id, storage_uuid)
