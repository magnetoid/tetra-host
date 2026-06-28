from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_COOLIFY,
    PROVIDER_MAILCOW,
    RESOURCE_TYPE_DATABASE,
    RESOURCE_TYPE_DNS_RECORD,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_MAILBOX,
    RESOURCE_TYPE_MAIL_DOMAIN,
    RESOURCE_TYPE_SERVER,
    RESOURCE_TYPE_SITE,
)
from app.services.cloudflare import CloudflareDNSRecord, CloudflareZone
from app.services.coolify import CoolifyApplication, CoolifyDatabase, CoolifyServer
from app.services.mailcow import MailcowDomain, MailcowMailbox


class TenantResourceFilter:
    def __init__(self, session: AsyncSession, tenant_id: str | None) -> None:
        self.session = session
        self.tenant_id = tenant_id or ""

    async def _strict_mode(self) -> bool:
        tenant_count = await self.session.scalar(select(func.count()).select_from(Tenant))
        # Fallback to legacy/global visibility while there is only one tenant in the system.
        # Once multiple tenants exist, mappings become authoritative.
        return bool(tenant_count and int(tenant_count) > 1)

    async def _mapped_values(self, *, provider: str, resource_type: str) -> set[str]:
        if not self.tenant_id:
            return set()
        rows = await self.session.scalars(
            select(TenantResource.external_id).where(
                TenantResource.tenant_id == self.tenant_id,
                TenantResource.provider == provider,
                TenantResource.resource_type == resource_type,
            )
        )
        return {value for value in rows.all() if value}

    async def is_resource_accessible(self, *, provider: str, resource_type: str, external_id: str) -> bool:
        mapped_ids = await self._mapped_values(provider=provider, resource_type=resource_type)
        if external_id in mapped_ids:
            return True
        return not mapped_ids and not await self._strict_mode()

    async def filter_sites(self, sites: list[CoolifyApplication]) -> list[CoolifyApplication]:
        mapped_ids = await self._mapped_values(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_SITE)
        if not mapped_ids and not await self._strict_mode():
            return sites
        return [site for site in sites if site.id in mapped_ids]

    async def filter_mail(
        self,
        domains: list[MailcowDomain],
        mailboxes: list[MailcowMailbox],
    ) -> tuple[list[MailcowDomain], list[MailcowMailbox]]:
        mapped_domains = await self._mapped_values(provider=PROVIDER_MAILCOW, resource_type=RESOURCE_TYPE_MAIL_DOMAIN)
        mapped_mailboxes = await self._mapped_values(provider=PROVIDER_MAILCOW, resource_type=RESOURCE_TYPE_MAILBOX)

        if not mapped_domains and not mapped_mailboxes and not await self._strict_mode():
            return domains, mailboxes

        allowed_domains = {domain.domain_name for domain in domains if domain.domain_name in mapped_domains}
        filtered_domains = [domain for domain in domains if domain.domain_name in allowed_domains]
        filtered_mailboxes = [
            mailbox
            for mailbox in mailboxes
            if mailbox.username in mapped_mailboxes or mailbox.domain in allowed_domains
        ]
        return filtered_domains, filtered_mailboxes

    async def filter_dns(
        self,
        zones: list[CloudflareZone],
        records: list[CloudflareDNSRecord],
        *,
        selected_zone: str,
    ) -> tuple[list[CloudflareZone], list[CloudflareDNSRecord], str]:
        mapped_zones = await self._mapped_values(provider=PROVIDER_CLOUDFLARE, resource_type=RESOURCE_TYPE_DNS_ZONE)
        mapped_records = await self._mapped_values(provider=PROVIDER_CLOUDFLARE, resource_type=RESOURCE_TYPE_DNS_RECORD)

        if not mapped_zones and not mapped_records and not await self._strict_mode():
            return zones, records, selected_zone

        filtered_zones = [zone for zone in zones if zone.id in mapped_zones]
        allowed_zone_ids = {zone.id for zone in filtered_zones}
        normalized_selected_zone = selected_zone if selected_zone in allowed_zone_ids else (filtered_zones[0].id if filtered_zones else "")
        filtered_records = [
            record
            for record in records
            if record.id in mapped_records or (normalized_selected_zone and record.name.endswith(tuple(zone.name for zone in filtered_zones if zone.id == normalized_selected_zone)))
        ]
        return filtered_zones, filtered_records, normalized_selected_zone


    async def filter_databases(self, databases: list[CoolifyDatabase]) -> list[CoolifyDatabase]:
        mapped_ids = await self._mapped_values(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_DATABASE)
        if not mapped_ids and not await self._strict_mode():
            return databases
        return [database for database in databases if database.id in mapped_ids]

    async def filter_servers(self, servers: list[CoolifyServer]) -> list[CoolifyServer]:
        mapped_ids = await self._mapped_values(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_SERVER)
        if not mapped_ids and not await self._strict_mode():
            return servers
        return [server for server in servers if server.id in mapped_ids]
