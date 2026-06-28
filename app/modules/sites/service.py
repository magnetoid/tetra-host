from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.services.coolify import CoolifyApplication, CoolifyClient, CoolifyDeployment
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter


class SitesService:
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

    async def deploy_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.deploy_application(application_id)

    async def start_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.start_application(application_id)

    async def restart_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> dict[str, object]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.restart_application(application_id)

    async def list_deployments_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        application_id: str,
    ) -> list[CoolifyDeployment]:
        await self._ensure_tenant_access(session, tenant_id, application_id)
        return await self.client.list_deployments_for_application(application_id)
