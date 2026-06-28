from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_resource import PROVIDER_CLOUDFLARE, RESOURCE_TYPE_DNS_ZONE
from app.services.cloudflare import CloudflareClient, CloudflareDNSRecord, CloudflareZone
from app.services.http import ProviderAPIError
from app.services.tenant_resources import TenantResourceFilter


class DnsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CloudflareClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )

    async def _ensure_zone_access(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        zone_id: str,
    ) -> None:
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_CLOUDFLARE,
            resource_type=RESOURCE_TYPE_DNS_ZONE,
            external_id=zone_id,
        )
        if not allowed:
            raise ProviderAPIError(
                service="Cloudflare",
                message="Zone is not assigned to this tenant.",
                status_code=403,
            )

    async def load(
        self,
        *,
        zone_id: str | None = None,
        refresh: bool = False,
    ) -> tuple[list[CloudflareZone], list[CloudflareDNSRecord]]:
        zones = await self.client.list_zones(refresh=refresh)
        selected_zone = zone_id or (zones[0].id if zones else "")
        records = await self.client.list_dns_records(selected_zone, refresh=refresh) if selected_zone else []
        return zones, records

    async def load_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        zone_id: str | None = None,
        refresh: bool = False,
    ) -> tuple[list[CloudflareZone], list[CloudflareDNSRecord], str]:
        zones, records = await self.load(zone_id=zone_id, refresh=refresh)
        selected_zone = zone_id or (zones[0].id if zones else "")
        return await TenantResourceFilter(session, tenant_id).filter_dns(
            zones,
            records,
            selected_zone=selected_zone,
        )

    async def create_record(
        self,
        zone_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        priority: int | None = None,
    ) -> dict:
        return await self.client.create_dns_record(
            zone_id,
            record_type=record_type,
            name=name,
            content=content,
            ttl=ttl,
            proxied=proxied,
            priority=priority,
        )

    async def update_record(
        self,
        zone_id: str,
        record_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        priority: int | None = None,
    ) -> dict:
        return await self.client.update_dns_record(
            zone_id,
            record_id,
            record_type=record_type,
            name=name,
            content=content,
            ttl=ttl,
            proxied=proxied,
            priority=priority,
        )

    async def delete_record(self, zone_id: str, record_id: str) -> dict:
        return await self.client.delete_dns_record(zone_id, record_id)

    # ── Tenant-guarded mutations (for the /api/v1 contract) ───────────────

    async def create_record_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        zone_id: str,
        *,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        priority: int | None = None,
    ) -> dict:
        await self._ensure_zone_access(session, tenant_id, zone_id)
        return await self.create_record(
            zone_id,
            record_type=record_type,
            name=name,
            content=content,
            ttl=ttl,
            proxied=proxied,
            priority=priority,
        )

    async def delete_record_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        zone_id: str,
        record_id: str,
    ) -> dict:
        await self._ensure_zone_access(session, tenant_id, zone_id)
        return await self.delete_record(zone_id, record_id)
