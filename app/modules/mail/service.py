"""Mail service — tenant-scoped Mailcow reads AND writes (Phase 2, ADR 0015).

Writes are gated by ENABLE_PROVIDER_ACTIONS and tenant ownership (TenantResource
rows, fail-closed). Creating a domain runs the full platform flow: mailcow domain →
DKIM generation → optional ESP relayhost assignment → best-effort DNS automation
(MX/SPF/DKIM/DMARC through the tenant's Cloudflare zone), returning a per-record
report instead of failing the whole operation on a DNS hiccup.
"""

import logging
import secrets
from typing import Any

from fastapi import Request
from sqlalchemy import delete, or_, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_MAILCOW,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_MAIL_DOMAIN,
    RESOURCE_TYPE_MAILBOX,
)
from app.modules.dns.service import DnsService
from app.services.http import ProviderAPIError
from app.services.mailcow import (
    MailcowAlias,
    MailcowAppPassword,
    MailcowClient,
    MailcowDomain,
    MailcowMailbox,
    MailcowQuarantineItem,
)
from app.services.tenant_resources import TenantResourceFilter

logger = logging.getLogger(__name__)

# App-password plaintext is write-only in mailcow (stored hashed, never echoed),
# so we generate a strong secret here and reveal it to the caller exactly once.
_APP_PW_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no ambiguous 0/o/1/l


def _generate_app_password() -> str:
    """5 groups of 4 unambiguous chars (e.g. xf29-kd81-…) — ~100 bits, readable."""
    groups = ["".join(secrets.choice(_APP_PW_ALPHABET) for _ in range(4)) for _ in range(5)]
    return "-".join(groups)


class MailService:
    def __init__(self, request: Request) -> None:
        self.request = request
        self.client = MailcowClient.from_settings(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
        )
        settings = get_settings()
        self.actions_enabled = settings.enable_provider_actions
        self.mail_hostname = settings.mail_hostname
        self.spf_record = settings.mail_spf_record
        self.dmarc_record = settings.mail_dmarc_record
        self.default_relayhost_id = settings.mail_default_relayhost_id

    # ── Reads ───────────────────────────────────────────────────────────────

    async def load(self, refresh: bool = False) -> tuple[list[MailcowDomain], list[MailcowMailbox]]:
        domains = await self.client.list_domains(refresh=refresh)
        mailboxes = await self.client.list_mailboxes(refresh=refresh)
        return domains, mailboxes

    async def load_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        refresh: bool = False,
    ) -> tuple[list[MailcowDomain], list[MailcowMailbox]]:
        domains, mailboxes = await self.load(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_mail(domains, mailboxes)

    async def aliases_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, refresh: bool = False
    ) -> list[MailcowAlias]:
        aliases = await self.client.list_aliases(refresh=refresh)
        return await TenantResourceFilter(session, tenant_id).filter_aliases(aliases)

    async def dkim_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, domain: str
    ) -> dict[str, str]:
        await self._ensure_domain_access(session, tenant_id, domain)
        dkim = await self.client.get_dkim(domain)
        selector = str(dkim.get("dkim_selector") or "dkim")
        txt = str(dkim.get("dkim_txt") or "")
        return {
            "domain": domain,
            "dkim_name": f"{selector}._domainkey.{domain}" if txt else "",
            "dkim_txt": txt,
        }

    # ── Guards ──────────────────────────────────────────────────────────────

    def _require_actions(self) -> None:
        if not self.actions_enabled:
            raise ProviderAPIError(
                service="Mailcow",
                message="Provider actions are disabled (ENABLE_PROVIDER_ACTIONS=false).",
                status_code=403,
            )

    async def _domain_accessible(
        self, session: AsyncSession, tenant_id: str | None, domain: str
    ) -> bool:
        return await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_MAILCOW,
            resource_type=RESOURCE_TYPE_MAIL_DOMAIN,
            external_id=domain,
        )

    async def _ensure_domain_access(
        self, session: AsyncSession, tenant_id: str | None, domain: str
    ) -> None:
        if not await self._domain_accessible(session, tenant_id, domain):
            # 404, not 403 — do not leak which mail domains exist on the platform.
            raise ProviderAPIError(
                service="Mailcow", message="Mail domain not found.", status_code=404
            )

    async def _mailbox_accessible(
        self, session: AsyncSession, tenant_id: str | None, username: str
    ) -> bool:
        """A mailbox is accessible if it's directly owned OR its domain is owned
        (domain owners implicitly own every mailbox under the domain)."""
        allowed = await TenantResourceFilter(session, tenant_id).is_resource_accessible(
            provider=PROVIDER_MAILCOW,
            resource_type=RESOURCE_TYPE_MAILBOX,
            external_id=username,
        )
        if not allowed and "@" in username:
            allowed = await self._domain_accessible(
                session, tenant_id, username.split("@", 1)[-1]
            )
        return allowed

    async def _ensure_mailbox_access(
        self, session: AsyncSession, tenant_id: str | None, username: str
    ) -> None:
        if not await self._mailbox_accessible(session, tenant_id, username):
            # 404, not 403 — don't leak which mailboxes exist on the platform.
            raise ProviderAPIError(
                service="Mailcow", message="Mailbox not found.", status_code=404
            )

    # ── Domain lifecycle ────────────────────────────────────────────────────

    async def create_domain_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        domain: str,
        *,
        description: str = "",
        quota_mb: int = 10240,
    ) -> dict[str, Any]:
        self._require_actions()
        logger.info("provisioning mail domain %s (tenant %s)", domain, tenant_id)
        await self.client.create_domain(
            domain,
            description=description,
            quota_mb=quota_mb,
            max_quota_mb=quota_mb,
            # The per-mailbox default must never exceed the domain cap.
            def_quota_mb=min(3072, max(1, quota_mb)),
        )

        # Register ownership immediately so scoping applies from the first read.
        if tenant_id:
            session.add(
                TenantResource(
                    tenant_id=tenant_id, provider=PROVIDER_MAILCOW,
                    resource_type=RESOURCE_TYPE_MAIL_DOMAIN, external_id=domain,
                    display_name=domain,
                )
            )
            await session.flush()

        # Everything past the provider create is best-effort BY CONTRACT: the domain
        # exists and ownership is registered — no enrichment failure (of ANY kind,
        # not just ProviderAPIError) may fail the request, or the ownership row
        # would roll back and orphan the mailcow domain.
        # DKIM: generate (may already exist — fine), then read the published key.
        dkim_name = dkim_txt = ""
        try:
            await self.client.generate_dkim(domain)
        except Exception:  # noqa: BLE001
            pass
        try:
            dkim = await self.client.get_dkim(domain)
            dkim_txt = str(dkim.get("dkim_txt") or "")
            if dkim_txt:
                selector = str(dkim.get("dkim_selector") or "dkim")
                dkim_name = f"{selector}._domainkey.{domain}"
        except Exception:  # noqa: BLE001
            logger.warning("could not read DKIM key for mail domain %s", domain)

        # ESP relay: platform default sender-dependent transport, best-effort.
        relay_assigned = False
        if self.default_relayhost_id:
            try:
                await self.client.assign_relayhost(domain, self.default_relayhost_id)
                relay_assigned = True
            except Exception:  # noqa: BLE001
                logger.warning("relayhost assignment failed for mail domain %s", domain)

        try:
            dns_zone, dns_records = await self._provision_mail_dns(
                session, tenant_id, domain, dkim_name=dkim_name, dkim_txt=dkim_txt
            )
        except Exception:  # noqa: BLE001
            logger.warning("mail DNS automation unavailable for %s", domain)
            dns_zone, dns_records = "", [
                {
                    "name": domain, "record_type": "*", "status": "skipped",
                    "detail": "DNS automation unavailable.",
                }
            ]
        return {
            "domain": domain,
            "dkim_name": dkim_name,
            "dkim_txt": dkim_txt,
            "relay_assigned": relay_assigned,
            "dns_zone": dns_zone,
            "dns_records": dns_records,
        }

    async def delete_domain_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, domain: str
    ) -> None:
        self._require_actions()
        await self._ensure_domain_access(session, tenant_id, domain)
        logger.info("deleting mail domain %s (tenant %s)", domain, tenant_id)
        await self.client.delete_domain(domain)
        # Unregister the domain and its mailboxes ACROSS ALL TENANTS — the provider
        # object is gone globally (a platform-scope admin can delete another
        # tenant's domain; leaving the owner's rows behind would fake ownership of
        # a nonexistent domain). DNS records are intentionally left in place
        # (removing records on a possibly-shared zone is riskier than leaving
        # stale ones — surfaced in the API response message).
        await session.execute(
            delete(TenantResource).where(
                TenantResource.provider == PROVIDER_MAILCOW,
                or_(
                    and_(
                        TenantResource.resource_type == RESOURCE_TYPE_MAIL_DOMAIN,
                        TenantResource.external_id == domain,
                    ),
                    and_(
                        TenantResource.resource_type == RESOURCE_TYPE_MAILBOX,
                        TenantResource.external_id.like(f"%@{domain}"),
                    ),
                ),
            )
        )

    # ── Mailboxes ───────────────────────────────────────────────────────────

    async def create_mailbox_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        *,
        local_part: str,
        domain: str,
        password: str,
        name: str = "",
        quota_mb: int = 3072,
    ) -> str:
        self._require_actions()
        await self._ensure_domain_access(session, tenant_id, domain)
        logger.info("creating mailbox on domain %s (tenant %s)", domain, tenant_id)
        await self.client.create_mailbox(
            local_part, domain, password=password, name=name, quota_mb=quota_mb
        )
        username = f"{local_part}@{domain}"
        if tenant_id:
            session.add(
                TenantResource(
                    tenant_id=tenant_id, provider=PROVIDER_MAILCOW,
                    resource_type=RESOURCE_TYPE_MAILBOX, external_id=username,
                    display_name=username,
                )
            )
            await session.flush()
        return username

    async def edit_mailbox_for_tenant(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        username: str,
        *,
        quota_mb: int | None = None,
        name: str | None = None,
        active: bool | None = None,
        password: str | None = None,
    ) -> None:
        self._require_actions()
        await self._ensure_mailbox_access(session, tenant_id, username)
        await self.client.edit_mailbox(
            username, quota_mb=quota_mb, name=name, active=active, password=password
        )

    async def delete_mailbox_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, username: str
    ) -> None:
        self._require_actions()
        await self._ensure_mailbox_access(session, tenant_id, username)
        await self.client.delete_mailbox(username)
        # Cross-tenant cleanup: the provider mailbox is gone for everyone.
        await session.execute(
            delete(TenantResource).where(
                TenantResource.provider == PROVIDER_MAILCOW,
                TenantResource.resource_type == RESOURCE_TYPE_MAILBOX,
                TenantResource.external_id == username,
            )
        )

    # ── Aliases ─────────────────────────────────────────────────────────────

    async def create_alias_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, address: str, goto: str
    ) -> None:
        self._require_actions()
        domain = address.split("@", 1)[-1] if "@" in address else ""
        if not domain:
            raise ProviderAPIError(
                service="Mailcow", message="Alias address must contain a domain.", status_code=422
            )
        await self._ensure_domain_access(session, tenant_id, domain)
        await self.client.create_alias(address, goto)

    async def delete_alias_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, alias_id: int
    ) -> None:
        self._require_actions()
        # list_aliases degrades to [] when unconfigured, which would masquerade as
        # a 404 here — surface the real 503 first (dormancy contract: writes 503).
        if not self.client.is_configured():
            raise ProviderAPIError(
                service="Mailcow", message="Mailcow is not configured.", status_code=503
            )
        aliases = await self.client.list_aliases(refresh=True)
        match = next((alias for alias in aliases if alias.id == alias_id), None)
        if match is None or not await self._domain_accessible(session, tenant_id, match.domain):
            raise ProviderAPIError(
                service="Mailcow", message="Alias not found.", status_code=404
            )
        await self.client.delete_alias(alias_id)

    # ── App passwords (per-mailbox IMAP/SMTP credentials) ────────────────────

    async def list_app_passwords_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, username: str
    ) -> list[MailcowAppPassword]:
        await self._ensure_mailbox_access(session, tenant_id, username)
        return await self.client.list_app_passwords(username)

    async def create_app_password_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, username: str, *, app_name: str
    ) -> dict[str, str]:
        """Create a purpose-scoped credential and return its plaintext ONCE.
        mailcow never echoes the secret back, so this response is the only place
        it's visible — the caller must show-and-forget it."""
        self._require_actions()
        await self._ensure_mailbox_access(session, tenant_id, username)
        name = app_name.strip() or "Tetra app password"
        password = _generate_app_password()
        await self.client.create_app_password(username, app_name=name, password=password)
        return {"app_name": name, "password": password}

    async def delete_app_password_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, username: str, app_passwd_id: int
    ) -> None:
        self._require_actions()
        await self._ensure_mailbox_access(session, tenant_id, username)
        # Confirm the id actually belongs to THIS mailbox before deleting — the id
        # space is global, so scoping by mailbox is what prevents cross-mailbox deletes.
        existing = await self.client.list_app_passwords(username)
        if not any(item.id == app_passwd_id for item in existing):
            raise ProviderAPIError(
                service="Mailcow", message="App password not found.", status_code=404
            )
        await self.client.delete_app_password(app_passwd_id)

    # ── Quarantine (held spam/rejected mail) ─────────────────────────────────

    async def _accessible_mail_scope(
        self, session: AsyncSession, tenant_id: str | None
    ) -> tuple[set[str], set[str]] | None:
        """(owned domains, owned mailboxes) for `tenant_id`, or None when
        unrestricted (platform scope). Used to scope quarantine by recipient.

        Derived from the authoritative TenantResource ownership rows — NOT from
        the live mailcow inventory (which could be stale/unconfigured and would
        wrongly narrow scope)."""
        if tenant_id is None:
            return None
        result = await session.execute(
            select(TenantResource.resource_type, TenantResource.external_id).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_MAILCOW,
                TenantResource.resource_type.in_(
                    [RESOURCE_TYPE_MAIL_DOMAIN, RESOURCE_TYPE_MAILBOX]
                ),
            )
        )
        domains: set[str] = set()
        mailboxes: set[str] = set()
        for rtype, external_id in result.all():
            if rtype == RESOURCE_TYPE_MAIL_DOMAIN:
                domains.add(external_id.strip().lower())
            else:
                mailboxes.add(external_id.strip().lower())
        return domains, mailboxes

    def _rcpt_in_scope(
        self, rcpt: str, scope: tuple[set[str], set[str]] | None
    ) -> bool:
        if scope is None:
            return True
        domains, mailboxes = scope
        rcpt = rcpt.strip().lower()
        if rcpt in mailboxes:
            return True
        return "@" in rcpt and rcpt.split("@", 1)[-1] in domains

    async def list_quarantine_for_tenant(
        self, session: AsyncSession, tenant_id: str | None
    ) -> list[MailcowQuarantineItem]:
        scope = await self._accessible_mail_scope(session, tenant_id)
        items = await self.client.list_quarantine()
        return [item for item in items if self._rcpt_in_scope(item.rcpt, scope)]

    async def _authorize_quarantine_ids(
        self, session: AsyncSession, tenant_id: str | None, ids: list[int]
    ) -> None:
        """Every targeted id must resolve to an in-scope recipient — otherwise a
        tenant could release/delete another tenant's held mail by guessing ids."""
        scope = await self._accessible_mail_scope(session, tenant_id)
        by_id = {item.id: item for item in await self.client.list_quarantine()}
        for qid in ids:
            item = by_id.get(qid)
            if item is None or not self._rcpt_in_scope(item.rcpt, scope):
                raise ProviderAPIError(
                    service="Mailcow", message="Quarantine item not found.", status_code=404
                )

    async def act_on_quarantine_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, ids: list[int], action: str
    ) -> None:
        self._require_actions()
        if not ids:
            raise ProviderAPIError(
                service="Mailcow", message="No quarantine items selected.", status_code=422
            )
        await self._authorize_quarantine_ids(session, tenant_id, ids)
        await self.client.act_on_quarantine(list(ids), action)

    async def delete_quarantine_for_tenant(
        self, session: AsyncSession, tenant_id: str | None, *, ids: list[int]
    ) -> None:
        self._require_actions()
        if not ids:
            raise ProviderAPIError(
                service="Mailcow", message="No quarantine items selected.", status_code=422
            )
        await self._authorize_quarantine_ids(session, tenant_id, ids)
        await self.client.delete_quarantine(list(ids))

    # ── Relayhosts (platform-level ESP credentials) ─────────────────────────

    async def list_relayhosts(self) -> list[dict[str, Any]]:
        """Safe projection of sender-dependent transports — NEVER includes the
        password fields mailcow returns. Platform-admin only at the route."""
        hosts = await self.client.list_relayhosts()
        return [
            {
                "id": int(host.get("id") or 0),
                "hostname": str(host.get("hostname") or ""),
                "username": str(host.get("username") or ""),
                "active": str(host.get("active", "1")) in {"1", "true", "True"},
                "used_by_domains": str(host.get("used_by_domains") or ""),
            }
            for host in hosts
        ]

    async def create_relayhost(self, *, hostname: str, username: str, password: str) -> int:
        """Create a sender-dependent transport; returns its id (0 if undetectable).
        Platform-admin only — enforced at the route (the ESP credential is a
        platform secret, not tenant data)."""
        self._require_actions()
        await self.client.create_relayhost(hostname, username, password)
        try:
            hosts = await self.client.list_relayhosts()
        except ProviderAPIError:
            return 0
        for host in reversed(hosts):
            if str(host.get("hostname")) == hostname and str(host.get("username")) == username:
                return int(host.get("id") or 0)
        return 0

    # ── DNS automation ──────────────────────────────────────────────────────

    def _planned_records(
        self, domain: str, *, dkim_name: str, dkim_txt: str
    ) -> list[tuple[str, str, str, int | None]]:
        planned: list[tuple[str, str, str, int | None]] = []
        if self.mail_hostname:
            planned.append(("MX", domain, self.mail_hostname, 10))
        planned.append(("TXT", domain, self.spf_record, None))
        if dkim_txt:
            planned.append(("TXT", dkim_name, dkim_txt, None))
        planned.append(("TXT", f"_dmarc.{domain}", self.dmarc_record, None))
        return planned

    async def _provision_mail_dns(
        self,
        session: AsyncSession,
        tenant_id: str | None,
        domain: str,
        *,
        dkim_name: str,
        dkim_txt: str,
    ) -> tuple[str, list[dict[str, str]]]:
        """Create MX/SPF/DKIM/DMARC in the tenant's matching Cloudflare zone.

        Entirely best-effort: every outcome is reported per record ("created" /
        "failed" / "skipped") and never fails the domain creation itself.
        """
        planned = self._planned_records(domain, dkim_name=dkim_name, dkim_txt=dkim_txt)

        def skipped(reason: str) -> tuple[str, list[dict[str, str]]]:
            return "", [
                {"name": name, "record_type": rtype, "status": "skipped", "detail": reason}
                for rtype, name, _content, _prio in planned
            ]

        dns = DnsService(self.request)
        if not dns.client.is_configured():
            return skipped("Cloudflare is not configured.")
        try:
            zones = await dns.client.list_zones()
        except ProviderAPIError as exc:
            return skipped(f"Could not list zones: {exc}")
        # Only zones the tenant can access are candidates. A foreign tenant's zone
        # must be indistinguishable from a nonexistent one (same uniform "no match"
        # path) — otherwise this endpoint becomes a cross-tenant zone-enumeration
        # oracle via the dns_zone/detail fields.
        tenant_filter = TenantResourceFilter(session, tenant_id)
        matches = []
        for zone in zones:
            if domain != zone.name and not domain.endswith(f".{zone.name}"):
                continue
            if await tenant_filter.is_resource_accessible(
                provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_DNS_ZONE,
                external_id=zone.id,
            ):
                matches.append(zone)
        if not matches:
            return skipped("No matching Cloudflare zone.")
        zone = max(matches, key=lambda z: len(z.name))

        report: list[dict[str, str]] = []
        for rtype, name, content, priority in planned:
            try:
                await dns.create_record_for_tenant(
                    session, tenant_id, zone.id,
                    record_type=rtype, name=name, content=content, priority=priority,
                )
                report.append(
                    {"name": name, "record_type": rtype, "status": "created", "detail": ""}
                )
            except ProviderAPIError as exc:
                report.append(
                    {"name": name, "record_type": rtype, "status": "failed", "detail": str(exc)}
                )
        return zone.name, report
