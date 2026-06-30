"""Servers service — tenant-scoped wrappers around the Coolify servers API."""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.coolify import CoolifyClient, CoolifyServer
from app.services.tenant_resources import TenantResourceFilter


class ServersService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CoolifyClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )

    async def list_servers(self, refresh: bool = False) -> list[CoolifyServer]:
        return await self.client.list_servers()

    async def list_servers_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        refresh: bool = False,
    ) -> list[CoolifyServer]:
        servers = await self.list_servers(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_servers(servers)
