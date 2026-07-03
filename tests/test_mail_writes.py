"""Mail write orchestration (Phase 2): tenant-scoped Mailcow writes + DNS automation.

Route-level tests: MailcowClient/CloudflareClient methods are monkeypatched (no
network), tenant ownership is driven by seeded TenantResource rows. Since tenants
are fail-closed, ownership denials are real 404s, not fall-open artifacts.
"""

import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.admin import ROLE_PLATFORM_ADMIN
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_MAILCOW,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_MAIL_DOMAIN,
    RESOURCE_TYPE_MAILBOX,
)
from app.modules.auth.service import AuthService
from app.services.cloudflare import CloudflareClient, CloudflareZone
from app.services.mailcow import MailcowAlias, MailcowClient


async def _seed(
    *, slug: str, email: str, role: str = "owner",
    mail_domains: tuple[str, ...] = (), zones: tuple[str, ...] = (),
    mailboxes: tuple[str, ...] = (),
) -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=email, full_name="Owner", role=role,
                password_hash=auth.hash_password("mail-pass"), is_active=True,
            )
        )
        for domain in mail_domains:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_MAILCOW,
                    resource_type=RESOURCE_TYPE_MAIL_DOMAIN, external_id=domain,
                    display_name=domain,
                )
            )
        for username in mailboxes:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_MAILCOW,
                    resource_type=RESOURCE_TYPE_MAILBOX, external_id=username,
                    display_name=username,
                )
            )
        for zone_id in zones:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_CLOUDFLARE,
                    resource_type=RESOURCE_TYPE_DNS_ZONE, external_id=zone_id,
                    display_name=zone_id,
                )
            )
        return tenant.id


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "mail-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _enable(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)


def _patch_mailcow_write(monkeypatch, name, recorder=None, result=None):
    async def fake(self, *args, **kwargs):
        if recorder is not None:
            recorder.append((name, args, kwargs))
        return result if result is not None else [{"type": "success", "msg": ["ok"]}]

    monkeypatch.setattr(MailcowClient, name, fake)


async def _resource_rows(tenant_id: str, resource_type: str) -> list[str]:
    async with session_scope() as session:
        rows = await session.scalars(
            select(TenantResource.external_id).where(
                TenantResource.tenant_id == tenant_id,
                TenantResource.provider == PROVIDER_MAILCOW,
                TenantResource.resource_type == resource_type,
            )
        )
        return sorted(rows.all())


# ── domain creation: mailcow + DKIM + DNS automation ────────────────────────


def test_create_mail_domain_full_flow(client, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(get_settings(), "mail_hostname", "mail.cloud-industry.com")
    calls: list = []
    _patch_mailcow_write(monkeypatch, "create_domain", calls)
    _patch_mailcow_write(monkeypatch, "generate_dkim", calls)

    async def fake_get_dkim(self, domain):
        return {"dkim_selector": "dkim", "dkim_txt": "v=DKIM1;k=rsa;p=MIIB"}

    monkeypatch.setattr(MailcowClient, "get_dkim", fake_get_dkim)

    monkeypatch.setattr(CloudflareClient, "is_configured", lambda self: True)

    async def fake_list_zones(self, refresh=False):
        return [CloudflareZone(id="z1", name="acme.test", status="active")]

    dns_created: list = []

    async def fake_create_record(
        self, zone_id, record_type, name, content, ttl=1, proxied=False, priority=None
    ):
        dns_created.append((zone_id, record_type, name, content, priority))
        return {"success": True}

    monkeypatch.setattr(CloudflareClient, "list_zones", fake_list_zones)
    monkeypatch.setattr(CloudflareClient, "create_dns_record", fake_create_record)

    tenant_id = asyncio.run(_seed(slug="md1", email="o@md1.test", zones=("z1",)))
    headers = _login(client, "o@md1.test")
    r = client.post("/api/v1/mail/domains", headers=headers, json={"domain": "acme.test"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["domain"] == "acme.test"
    assert body["dkim_name"] == "dkim._domainkey.acme.test"
    assert body["dkim_txt"].startswith("v=DKIM1")
    assert body["dns_zone"] == "acme.test"
    by_type = {(rec["record_type"], rec["name"]): rec["status"] for rec in body["dns_records"]}
    assert by_type[("MX", "acme.test")] == "created"
    assert by_type[("TXT", "acme.test")] == "created"  # SPF
    assert by_type[("TXT", "dkim._domainkey.acme.test")] == "created"
    assert by_type[("TXT", "_dmarc.acme.test")] == "created"
    assert ("z1", "MX", "acme.test", "mail.cloud-industry.com", 10) in dns_created
    # Domain registered to the tenant for immediate scoping.
    assert asyncio.run(_resource_rows(tenant_id, RESOURCE_TYPE_MAIL_DOMAIN)) == ["acme.test"]


def test_create_mail_domain_actions_disabled(client, monkeypatch):
    asyncio.run(_seed(slug="md2", email="o@md2.test"))
    headers = _login(client, "o@md2.test")
    r = client.post("/api/v1/mail/domains", headers=headers, json={"domain": "x.test"})
    assert r.status_code == 403


def test_create_mail_domain_without_matching_zone_reports_skipped(client, monkeypatch):
    _enable(monkeypatch)
    _patch_mailcow_write(monkeypatch, "create_domain")
    _patch_mailcow_write(monkeypatch, "generate_dkim")

    async def fake_get_dkim(self, domain):
        return {}

    monkeypatch.setattr(MailcowClient, "get_dkim", fake_get_dkim)
    monkeypatch.setattr(CloudflareClient, "is_configured", lambda self: True)

    async def fake_list_zones(self, refresh=False):
        return [CloudflareZone(id="z9", name="other.tld", status="active")]

    monkeypatch.setattr(CloudflareClient, "list_zones", fake_list_zones)

    asyncio.run(_seed(slug="md3", email="o@md3.test"))
    headers = _login(client, "o@md3.test")
    r = client.post("/api/v1/mail/domains", headers=headers, json={"domain": "acme.test"})
    assert r.status_code == 200
    body = r.json()
    assert body["dns_zone"] == ""
    assert body["dns_records"] and all(
        rec["status"] == "skipped" for rec in body["dns_records"]
    )


def test_create_mail_domain_assigns_default_relay(client, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(get_settings(), "mail_default_relayhost_id", 2, raising=False)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "create_domain", calls)
    _patch_mailcow_write(monkeypatch, "generate_dkim", calls)
    _patch_mailcow_write(monkeypatch, "assign_relayhost", calls)

    async def fake_get_dkim(self, domain):
        return {}

    monkeypatch.setattr(MailcowClient, "get_dkim", fake_get_dkim)
    monkeypatch.setattr(CloudflareClient, "is_configured", lambda self: False)

    asyncio.run(_seed(slug="md4", email="o@md4.test"))
    headers = _login(client, "o@md4.test")
    r = client.post("/api/v1/mail/domains", headers=headers, json={"domain": "acme.test"})
    assert r.status_code == 200
    assert r.json()["relay_assigned"] is True
    assert ("assign_relayhost", ("acme.test", 2), {}) in calls


# ── domain deletion ─────────────────────────────────────────────────────────


def test_delete_mail_domain_ownership_and_cleanup(client, monkeypatch):
    _enable(monkeypatch)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "delete_domain", calls)

    owner_id = asyncio.run(
        _seed(
            slug="dd1", email="o@dd1.test",
            mail_domains=("acme.test",), mailboxes=("info@acme.test", "kept@other.test"),
        )
    )
    asyncio.run(_seed(slug="dd2", email="o@dd2.test"))

    foreign = _login(client, "o@dd2.test")
    assert (
        client.delete("/api/v1/mail/domains/acme.test", headers=foreign).status_code == 404
    )

    owner = _login(client, "o@dd1.test")
    r = client.delete("/api/v1/mail/domains/acme.test", headers=owner)
    assert r.status_code == 200
    assert ("delete_domain", ("acme.test",), {}) in calls
    assert asyncio.run(_resource_rows(owner_id, RESOURCE_TYPE_MAIL_DOMAIN)) == []
    # The domain's mailboxes are unregistered too; unrelated ones survive.
    assert asyncio.run(_resource_rows(owner_id, RESOURCE_TYPE_MAILBOX)) == ["kept@other.test"]


# ── mailboxes ───────────────────────────────────────────────────────────────


def test_create_mailbox_requires_owned_domain(client, monkeypatch):
    _enable(monkeypatch)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "create_mailbox", calls)

    tenant_id = asyncio.run(_seed(slug="mb1", email="o@mb1.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@mb1.test")

    r = client.post(
        "/api/v1/mail/mailboxes", headers=headers,
        json={"local_part": "info", "domain": "foreign.test", "password": "s3cret-pw"},
    )
    assert r.status_code == 404

    r = client.post(
        "/api/v1/mail/mailboxes", headers=headers,
        json={"local_part": "info", "domain": "acme.test", "password": "s3cret-pw"},
    )
    assert r.status_code == 200
    assert calls and calls[0][0] == "create_mailbox"
    assert asyncio.run(_resource_rows(tenant_id, RESOURCE_TYPE_MAILBOX)) == ["info@acme.test"]


def test_delete_mailbox_via_domain_ownership(client, monkeypatch):
    _enable(monkeypatch)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "delete_mailbox", calls)

    asyncio.run(_seed(slug="mb2", email="o@mb2.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@mb2.test")
    r = client.delete("/api/v1/mail/mailboxes/info@acme.test", headers=headers)
    assert r.status_code == 200
    assert ("delete_mailbox", ("info@acme.test",), {}) in calls

    assert (
        client.delete("/api/v1/mail/mailboxes/x@foreign.test", headers=headers).status_code
        == 404
    )


# ── aliases ─────────────────────────────────────────────────────────────────


def _patch_aliases(monkeypatch):
    async def fake_list_aliases(self, refresh=False):
        return [
            MailcowAlias(id=6, address="sales@acme.test", goto="info@acme.test", domain="acme.test"),
            MailcowAlias(id=7, address="x@foreign.test", goto="y@foreign.test", domain="foreign.test"),
        ]

    monkeypatch.setattr(MailcowClient, "list_aliases", fake_list_aliases)


def test_aliases_scoped_to_owned_domains(client, monkeypatch):
    _patch_aliases(monkeypatch)
    asyncio.run(_seed(slug="al1", email="o@al1.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@al1.test")
    r = client.get("/api/v1/mail/aliases", headers=headers)
    assert r.status_code == 200
    assert [a["id"] for a in r.json()] == [6]


def test_create_alias_requires_owned_domain(client, monkeypatch):
    _enable(monkeypatch)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "create_alias", calls)

    asyncio.run(_seed(slug="al2", email="o@al2.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@al2.test")

    r = client.post(
        "/api/v1/mail/aliases", headers=headers,
        json={"address": "sales@foreign.test", "goto": "x@foreign.test"},
    )
    assert r.status_code == 404

    r = client.post(
        "/api/v1/mail/aliases", headers=headers,
        json={"address": "sales@acme.test", "goto": "info@acme.test"},
    )
    assert r.status_code == 200
    assert ("create_alias", ("sales@acme.test", "info@acme.test"), {}) in calls


def test_delete_alias_checks_ownership(client, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(MailcowClient, "is_configured", lambda self: True)
    _patch_aliases(monkeypatch)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "delete_alias", calls)

    asyncio.run(_seed(slug="al3", email="o@al3.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@al3.test")

    assert client.delete("/api/v1/mail/aliases/7", headers=headers).status_code == 404
    assert client.delete("/api/v1/mail/aliases/99", headers=headers).status_code == 404
    assert client.delete("/api/v1/mail/aliases/6", headers=headers).status_code == 200
    assert ("delete_alias", (6,), {}) in calls


# ── DKIM read ───────────────────────────────────────────────────────────────


def test_dkim_endpoint_requires_ownership(client, monkeypatch):
    async def fake_get_dkim(self, domain):
        return {"dkim_selector": "dkim", "dkim_txt": "v=DKIM1;p=X"}

    monkeypatch.setattr(MailcowClient, "get_dkim", fake_get_dkim)
    asyncio.run(_seed(slug="dk1", email="o@dk1.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@dk1.test")

    r = client.get("/api/v1/mail/domains/acme.test/dkim", headers=headers)
    assert r.status_code == 200
    assert r.json()["dkim_name"] == "dkim._domainkey.acme.test"

    assert (
        client.get("/api/v1/mail/domains/foreign.test/dkim", headers=headers).status_code
        == 404
    )


# ── relayhosts (platform admin only) ────────────────────────────────────────


def test_relayhost_requires_platform_admin(client, monkeypatch):
    _enable(monkeypatch)
    calls: list = []
    _patch_mailcow_write(monkeypatch, "create_relayhost", calls)

    async def fake_list_relayhosts(self):
        return [{"id": 3, "hostname": "smtp.postmarkapp.com:587", "username": "u"}]

    monkeypatch.setattr(MailcowClient, "list_relayhosts", fake_list_relayhosts)

    asyncio.run(_seed(slug="rh1", email="o@rh1.test"))
    owner = _login(client, "o@rh1.test")
    payload = {"hostname": "smtp.postmarkapp.com:587", "username": "u", "password": "p"}
    assert client.post("/api/v1/mail/relayhosts", headers=owner, json=payload).status_code == 403

    asyncio.run(_seed(slug="rh2", email="p@rh2.test", role=ROLE_PLATFORM_ADMIN))
    admin = _login(client, "p@rh2.test")
    r = client.post("/api/v1/mail/relayhosts", headers=admin, json=payload)
    assert r.status_code == 200
    assert r.json()["relayhost_id"] == 3
    assert calls and calls[0][0] == "create_relayhost"


# ── Adversarial-review regressions ──────────────────────────────────────────


def test_dns_automation_is_not_a_zone_enumeration_oracle(client, monkeypatch):
    """A foreign tenant's zone must be indistinguishable from no zone at all —
    same skipped report, never the foreign zone's name."""
    _enable(monkeypatch)
    _patch_mailcow_write(monkeypatch, "create_domain")
    _patch_mailcow_write(monkeypatch, "generate_dkim")

    async def fake_get_dkim(self, domain):
        return {}

    monkeypatch.setattr(MailcowClient, "get_dkim", fake_get_dkim)
    monkeypatch.setattr(CloudflareClient, "is_configured", lambda self: True)

    async def fake_list_zones(self, refresh=False):
        return [CloudflareZone(id="zb", name="example.com", status="active")]

    created: list = []

    async def fake_create_record(self, *a, **k):  # pragma: no cover
        created.append(a)
        return {"success": True}

    monkeypatch.setattr(CloudflareClient, "list_zones", fake_list_zones)
    monkeypatch.setattr(CloudflareClient, "create_dns_record", fake_create_record)

    # Zone zb belongs to ANOTHER tenant; the probing tenant owns nothing.
    asyncio.run(_seed(slug="zo1", email="o@zo1.test", zones=("zb",)))
    asyncio.run(_seed(slug="zo2", email="o@zo2.test"))
    headers = _login(client, "o@zo2.test")
    r = client.post(
        "/api/v1/mail/domains", headers=headers, json={"domain": "probe.example.com"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dns_zone"] == ""  # never the foreign zone's name
    assert all(rec["status"] == "skipped" for rec in body["dns_records"])
    assert all("not assigned" not in rec["detail"] for rec in body["dns_records"])
    assert created == []


def test_domain_create_survives_raw_transport_error_in_enrichment(client, monkeypatch):
    """A non-ProviderAPIError crash after the provider create must not 500 the
    request (which would roll back ownership and orphan the mailcow domain)."""
    import httpx as _httpx

    _enable(monkeypatch)
    _patch_mailcow_write(monkeypatch, "create_domain")

    async def exploding_dkim(self, domain):
        raise _httpx.ConnectTimeout("mailcow briefly unreachable")

    monkeypatch.setattr(MailcowClient, "generate_dkim", exploding_dkim)
    monkeypatch.setattr(MailcowClient, "get_dkim", exploding_dkim)
    monkeypatch.setattr(CloudflareClient, "is_configured", lambda self: False)

    tenant_id = asyncio.run(_seed(slug="tx1", email="o@tx1.test"))
    headers = _login(client, "o@tx1.test")
    r = client.post("/api/v1/mail/domains", headers=headers, json={"domain": "acme.test"})
    assert r.status_code == 200
    assert asyncio.run(_resource_rows(tenant_id, RESOURCE_TYPE_MAIL_DOMAIN)) == ["acme.test"]


def test_platform_scope_delete_cleans_owner_tenant_rows(client, monkeypatch):
    """When a platform-scope admin deletes a domain, the real owner's resource rows
    must go too — the provider object is gone for everyone."""
    _enable(monkeypatch)
    _patch_mailcow_write(monkeypatch, "delete_domain")

    owner_id = asyncio.run(
        _seed(slug="ps1", email="o@ps1.test", mail_domains=("acme.test",),
              mailboxes=("info@acme.test",))
    )
    # Platform-scope tenant (fall-open) — can see/delete everything.
    async def make_platform(slug, email):
        tenant_id = await _seed(slug=slug, email=email)
        async with session_scope() as session:
            tenant = await session.get(Tenant, tenant_id)
            tenant.is_platform_scope = True

    asyncio.run(make_platform("ps2", "o@ps2.test"))
    headers = _login(client, "o@ps2.test")
    assert client.delete("/api/v1/mail/domains/acme.test", headers=headers).status_code == 200
    assert asyncio.run(_resource_rows(owner_id, RESOURCE_TYPE_MAIL_DOMAIN)) == []
    assert asyncio.run(_resource_rows(owner_id, RESOURCE_TYPE_MAILBOX)) == []


def test_delete_alias_unconfigured_is_503_not_404(client, monkeypatch):
    _enable(monkeypatch)
    asyncio.run(_seed(slug="ua1", email="o@ua1.test", mail_domains=("acme.test",)))
    headers = _login(client, "o@ua1.test")
    # Test env has no MAILCOW_URL → list_aliases would return [] and fake a 404.
    assert client.delete("/api/v1/mail/aliases/6", headers=headers).status_code == 503


def test_relayhost_list_platform_only_and_never_leaks_password(client, monkeypatch):
    async def fake_list_relayhosts(self):
        return [
            {"id": 3, "hostname": "smtp.postmarkapp.com:587", "username": "u",
             "active": "1", "used_by_domains": "acme.test", "password": "SECRET",
             "password_short": "SEC..."}
        ]

    monkeypatch.setattr(MailcowClient, "list_relayhosts", fake_list_relayhosts)

    asyncio.run(_seed(slug="rl1", email="o@rl1.test"))
    owner = _login(client, "o@rl1.test")
    assert client.get("/api/v1/mail/relayhosts", headers=owner).status_code == 403

    asyncio.run(_seed(slug="rl2", email="p@rl2.test", role=ROLE_PLATFORM_ADMIN))
    admin = _login(client, "p@rl2.test")
    r = client.get("/api/v1/mail/relayhosts", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body[0]["id"] == 3 and body[0]["used_by_domains"] == "acme.test"
    assert "password" not in r.text and "SECRET" not in r.text


def test_domain_quota_must_be_positive(client, monkeypatch):
    _enable(monkeypatch)
    asyncio.run(_seed(slug="qb1", email="o@qb1.test"))
    headers = _login(client, "o@qb1.test")
    r = client.post(
        "/api/v1/mail/domains", headers=headers, json={"domain": "acme.test", "quota_mb": 0}
    )
    assert r.status_code == 422
