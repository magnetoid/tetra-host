from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cloudflare import CloudflareClient, CloudflareDNSRecord, CloudflareZone
from app.services.tenant_resources import TenantResourceFilter


class DnsService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = CloudflareClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
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
