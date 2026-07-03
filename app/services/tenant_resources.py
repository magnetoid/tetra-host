from sqlalchemy import select
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
from app.services.mailcow import MailcowAlias, MailcowDomain, MailcowMailbox


class TenantResourceFilter:
    def __init__(self, session: AsyncSession, tenant_id: str | None) -> None:
        self.session = session
        self.tenant_id = tenant_id or ""
        self._platform_scope_cache: bool | None = None

    async def _is_platform_scope(self) -> bool:
        """Return True only if this tenant's row has is_platform_scope=True.

        Deny by default: missing tenant_id, empty string, or a missing/non-
        platform-scope row all return False.
        """
        if self._platform_scope_cache is not None:
            return self._platform_scope_cache

        if not self.tenant_id:
            self._platform_scope_cache = False
            return False

        row = await self.session.scalar(
            select(Tenant.is_platform_scope).where(Tenant.id == self.tenant_id)
        )
        result = bool(row)
        self._platform_scope_cache = result
        return result

    async def _fall_open(self) -> bool:
        """Fall open ONLY for tenants with is_platform_scope=True."""
        return await self._is_platform_scope()

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
        return external_id in mapped_ids or await self._fall_open()

    async def filter_sites(self, sites: list[CoolifyApplication]) -> list[CoolifyApplication]:
        if await self._fall_open():
            return sites
        mapped_ids = await self._mapped_values(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_SITE)
        return [site for site in sites if site.id in mapped_ids]

    async def filter_mail(
        self,
        domains: list[MailcowDomain],
        mailboxes: list[MailcowMailbox],
    ) -> tuple[list[MailcowDomain], list[MailcowMailbox]]:
        if await self._fall_open():
            return domains, mailboxes

        mapped_domains = await self._mapped_values(provider=PROVIDER_MAILCOW, resource_type=RESOURCE_TYPE_MAIL_DOMAIN)
        mapped_mailboxes = await self._mapped_values(provider=PROVIDER_MAILCOW, resource_type=RESOURCE_TYPE_MAILBOX)

        allowed_domains = {domain.domain_name for domain in domains if domain.domain_name in mapped_domains}
        filtered_domains = [domain for domain in domains if domain.domain_name in allowed_domains]
        filtered_mailboxes = [
            mailbox
            for mailbox in mailboxes
            if mailbox.username in mapped_mailboxes or mailbox.domain in allowed_domains
        ]
        return filtered_domains, filtered_mailboxes

    async def filter_aliases(self, aliases: list[MailcowAlias]) -> list[MailcowAlias]:
        """Aliases are scoped by their domain — an alias is visible iff its domain is
        mapped to the tenant (there is no per-alias TenantResource type)."""
        if await self._fall_open():
            return aliases
        mapped_domains = await self._mapped_values(
            provider=PROVIDER_MAILCOW, resource_type=RESOURCE_TYPE_MAIL_DOMAIN
        )
        return [alias for alias in aliases if alias.domain in mapped_domains]

    async def filter_dns(
        self,
        zones: list[CloudflareZone],
        records: list[CloudflareDNSRecord],
        *,
        selected_zone: str,
    ) -> tuple[list[CloudflareZone], list[CloudflareDNSRecord], str]:
        if await self._fall_open():
            return zones, records, selected_zone

        mapped_zones = await self._mapped_values(provider=PROVIDER_CLOUDFLARE, resource_type=RESOURCE_TYPE_DNS_ZONE)
        mapped_records = await self._mapped_values(provider=PROVIDER_CLOUDFLARE, resource_type=RESOURCE_TYPE_DNS_RECORD)

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
        if await self._fall_open():
            return databases
        mapped_ids = await self._mapped_values(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_DATABASE)
        return [database for database in databases if database.id in mapped_ids]

    async def filter_servers(self, servers: list[CoolifyServer]) -> list[CoolifyServer]:
        if await self._fall_open():
            return servers
        mapped_ids = await self._mapped_values(provider=PROVIDER_COOLIFY, resource_type=RESOURCE_TYPE_SERVER)
        return [server for server in servers if server.id in mapped_ids]
