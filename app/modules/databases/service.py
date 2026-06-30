"""Databases service — tenant-scoped wrappers around the Coolify databases API."""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.coolify import CoolifyClient, CoolifyDatabase
from app.services.tenant_resources import TenantResourceFilter


class DatabasesService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CoolifyClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
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
