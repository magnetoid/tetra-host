"""Domains hub (ADR 0019): one row per domain the account owns, across providers.

A domain is account-level, not a service: its DNS zone (Cloudflare), its mail
(Mailcow) and the hostnames that route to services (Tetra Engine) are three views
of the same name. This joins them by apex at read time; nothing new is stored.

Each provider is read on its own, so one being down degrades its column only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Domain
from app.modules.dns.service import DnsService
from app.modules.domains.service import DomainsService
from app.modules.mail.service import MailService
from app.modules.workspaces.service import AppRow, WorkspaceService
from app.services.cloudflare import CloudflareZone
from app.services.http import ProviderAPIError
from app.services.mailcow import MailcowDomain
from app.services.tenant_resources import TenantResourceFilter

logger = logging.getLogger(__name__)

# Second-level labels under which registrations sit one level deeper (example.co.uk).
# Only used for hostnames that match no zone or mail domain the account has.
_SECOND_LEVEL = {"co", "com", "net", "org", "gov", "edu", "ac"}


@dataclass(frozen=True)
class ServiceRef:
    name: str
    kind: str
    project_slug: str
    environment_slug: str


@dataclass(frozen=True)
class HostnameEntry:
    id: str
    hostname: str
    status: str
    stack: str
    service: ServiceRef | None


@dataclass(frozen=True)
class MailEntry:
    domain_name: str
    mailboxes: int
    aliases: int
    active: bool


@dataclass(frozen=True)
class ZoneEntry:
    id: str
    status: str
    paused: bool


@dataclass
class DomainEntry:
    name: str
    zone: ZoneEntry | None = None
    mail: list[MailEntry] = field(default_factory=list)
    hostnames: list[HostnameEntry] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderState:
    name: str
    status: str  # connected | not_configured | degraded
    detail: str = ""


@dataclass(frozen=True)
class DomainsOverview:
    domains: list[DomainEntry]
    providers: list[ProviderState]


def _normalize(name: str) -> str:
    return name.strip().strip(".").lower()


def registrable_guess(hostname: str) -> str:
    """Best-effort apex for a hostname no known zone covers: the last two labels,
    or three under a common second-level label (shop.example.co.uk → example.co.uk)."""
    labels = _normalize(hostname).split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    if len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _covering(name: str, apexes: list[str]) -> str | None:
    """The longest known apex that ``name`` equals or sits under."""
    best = None
    for apex in apexes:
        if (name == apex or name.endswith("." + apex)) and (best is None or len(apex) > len(best)):
            best = apex
    return best


def build_overview(
    zones: list[CloudflareZone],
    mail_domains: list[MailcowDomain],
    hostnames: list[Domain],
    services: dict[str, ServiceRef],
) -> list[DomainEntry]:
    """Group zones, mail domains and hostnames under one apex each.

    Zones define apexes first; a mail domain or hostname joins the zone that covers
    it, else the mail domain's own name, else a registrable guess. Pure, so the
    grouping rules are tested without providers.
    """
    entries: dict[str, DomainEntry] = {}

    def entry(name: str) -> DomainEntry:
        return entries.setdefault(name, DomainEntry(name=name))

    for zone in zones:
        entry(_normalize(zone.name)).zone = ZoneEntry(
            id=zone.id, status=zone.status, paused=zone.paused
        )

    for domain in mail_domains:
        name = _normalize(domain.domain_name)
        apex = _covering(name, list(entries)) or name
        entry(apex).mail.append(
            MailEntry(
                domain_name=name, mailboxes=domain.mailboxes,
                aliases=domain.aliases, active=domain.active,
            )
        )

    for host in hostnames:
        name = _normalize(host.hostname)
        apex = _covering(name, list(entries)) or registrable_guess(name)
        entry(apex).hostnames.append(
            HostnameEntry(
                id=host.id, hostname=name, status=host.status,
                stack=host.project, service=services.get(host.project),
            )
        )

    for item in entries.values():
        item.mail.sort(key=lambda m: m.domain_name)
        item.hostnames.sort(key=lambda h: h.hostname)
    return sorted(entries.values(), key=lambda e: e.name)


def _service_refs(rows: list[AppRow]) -> dict[str, ServiceRef]:
    return {
        row.app.external_id: ServiceRef(
            name=row.app.name, kind=row.app.kind,
            project_slug=row.project.slug, environment_slug=row.environment.slug,
        )
        for row in rows
    }


class DomainsOverviewService:
    def __init__(self, request: Request, session: AsyncSession) -> None:
        self.request = request
        self.session = session

    async def _zones(self, tenant_id: str | None) -> tuple[list[CloudflareZone], ProviderState]:
        client = DnsService(self.request).client
        if not client.is_configured():
            return [], ProviderState("Cloudflare", "not_configured", "Token missing")
        try:
            zones = await client.list_zones()
        except ProviderAPIError as exc:
            logger.warning("domains overview: cloudflare unavailable: %s", exc)
            return [], ProviderState("Cloudflare", "degraded", str(exc))
        zones, _, _ = await TenantResourceFilter(self.session, tenant_id).filter_dns(
            zones, [], selected_zone=""
        )
        return zones, ProviderState("Cloudflare", "connected", f"{len(zones)} zones")

    async def _mail(self, tenant_id: str | None) -> tuple[list[MailcowDomain], ProviderState]:
        service = MailService(self.request)
        if not service.client.is_configured():
            return [], ProviderState("Mailcow", "not_configured", "Credentials missing")
        try:
            domains = await service.client.list_domains()
        except ProviderAPIError as exc:
            logger.warning("domains overview: mailcow unavailable: %s", exc)
            return [], ProviderState("Mailcow", "degraded", str(exc))
        domains, _ = await TenantResourceFilter(self.session, tenant_id).filter_mail(domains, [])
        return domains, ProviderState("Mailcow", "connected", f"{len(domains)} mail domains")

    async def load(self, tenant_id: str | None) -> DomainsOverview:
        zones, dns_state = await self._zones(tenant_id)
        mail, mail_state = await self._mail(tenant_id)
        hostnames = await DomainsService().list_for_tenant(self.session, tenant_id)
        rows = (
            await WorkspaceService(self.session).list_apps(tenant_id=tenant_id)
            if tenant_id
            else []
        )
        return DomainsOverview(
            domains=build_overview(zones, mail, hostnames, _service_refs(rows)),
            providers=[dns_state, mail_state],
        )

    async def get(self, tenant_id: str | None, name: str) -> DomainEntry | None:
        overview = await self.load(tenant_id)
        wanted = _normalize(name)
        return next((d for d in overview.domains if d.name == wanted), None)
