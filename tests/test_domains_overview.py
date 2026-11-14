"""Domains hub (ADR 0019): zones, mail domains and hostnames joined by apex."""

import asyncio

from app.db import session_scope
from app.models import Domain, Environment, TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    PROVIDER_MAILCOW,
    RESOURCE_TYPE_DNS_ZONE,
    RESOURCE_TYPE_MAIL_DOMAIN,
)
from app.modules.domains.overview import ServiceRef, build_overview, registrable_guess
from app.modules.workspaces.service import WorkspaceService
from app.services.cloudflare import CloudflareZone
from app.services.http import ProviderAPIError
from app.services.mailcow import MailcowDomain
from tests.test_databases import _headers, _seed

ZONES = [
    CloudflareZone(id="z-acme", name="acme.test", status="active"),
    CloudflareZone(id="z-other", name="other.test", status="active"),
]
MAIL = [
    MailcowDomain(domain_name="acme.test", mailboxes=3, aliases=1),
    MailcowDomain(domain_name="news.acme.test", mailboxes=1),
    MailcowDomain(domain_name="solo.test", mailboxes=2),
    MailcowDomain(domain_name="theirs.test"),
]


def _host(hostname: str, project: str = "web", status: str = "verified") -> Domain:
    return Domain(id=f"d-{hostname}", tenant_id="t", project=project, hostname=hostname, status=status)


# ── Grouping rules (pure) ────────────────────────────────────────────────────


def test_registrable_guess():
    assert registrable_guess("shop.example.com") == "example.com"
    assert registrable_guess("shop.example.co.uk") == "example.co.uk"
    assert registrable_guess("Example.COM.") == "example.com"
    assert registrable_guess("localhost") == "localhost"


def test_build_overview_joins_by_apex():
    ref = ServiceRef(name="web", kind="app", project_slug="site", environment_slug="production")
    entries = build_overview(
        [ZONES[0]],
        MAIL[:3],
        [_host("www.acme.test"), _host("api.acme.test", project="api"), _host("blog.solo.test"),
         _host("x.y.example.co.uk", project="other")],
        {"web": ref},
    )
    by_name = {e.name: e for e in entries}
    assert list(by_name) == ["acme.test", "example.co.uk", "solo.test"]

    acme = by_name["acme.test"]
    assert acme.zone and acme.zone.id == "z-acme"
    assert [m.domain_name for m in acme.mail] == ["acme.test", "news.acme.test"]
    assert [(h.hostname, h.service) for h in acme.hostnames] == [
        ("api.acme.test", None), ("www.acme.test", ref),
    ]

    # A mail domain without a zone is its own apex, and hostnames join it.
    solo = by_name["solo.test"]
    assert solo.zone is None and [h.hostname for h in solo.hostnames] == ["blog.solo.test"]


def test_longest_zone_wins():
    entries = build_overview(
        [CloudflareZone(id="a", name="acme.test", status="active"),
         CloudflareZone(id="b", name="eu.acme.test", status="active")],
        [], [_host("shop.eu.acme.test")], {},
    )
    by_name = {e.name: e for e in entries}
    assert by_name["eu.acme.test"].hostnames and not by_name["acme.test"].hostnames


# ── API ─────────────────────────────────────────────────────────────────────


def _fake_providers(monkeypatch, *, mail_down: bool = False):
    async def list_zones(self, refresh=False):
        return ZONES

    async def list_domains(self, refresh=False):
        if mail_down:
            raise ProviderAPIError(service="Mailcow", message="mailcow is down", status_code=502)
        return MAIL

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.list_zones", list_zones)
    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.is_configured", lambda self: True)
    monkeypatch.setattr("app.services.mailcow.MailcowClient.list_domains", list_domains)
    monkeypatch.setattr("app.services.mailcow.MailcowClient.is_configured", lambda self: True)


async def _own(tenant_id: str) -> None:
    async with session_scope() as session:
        session.add_all([
            TenantResource(tenant_id=tenant_id, provider=PROVIDER_CLOUDFLARE,
                           resource_type=RESOURCE_TYPE_DNS_ZONE, external_id="z-acme",
                           display_name="acme.test"),
            TenantResource(tenant_id=tenant_id, provider=PROVIDER_MAILCOW,
                           resource_type=RESOURCE_TYPE_MAIL_DOMAIN, external_id="acme.test",
                           display_name="acme.test"),
            Domain(tenant_id=tenant_id, project="acme-web", hostname="www.acme.test",
                   status="verified"),
        ])


async def _place(env_id: str, stack: str) -> None:
    async with session_scope() as session:
        env = await session.get(Environment, env_id)
        await WorkspaceService(session).place(env, stack, kind="app", name=stack)


def test_overview_is_tenant_scoped_and_links_services(client, monkeypatch):
    acme = asyncio.run(_seed("acme"))
    beta = asyncio.run(_seed("beta"))
    asyncio.run(_own(acme))
    _fake_providers(monkeypatch)
    h = _headers(client, "acme")

    client.post("/api/v1/teams/acme/projects", json={"name": "site"}, headers=h)
    envs = client.get("/api/v1/teams/acme/projects/site/environments", headers=h).json()
    asyncio.run(_place(next(e["id"] for e in envs if e["slug"] == "production"), "acme-web"))

    r = client.get("/api/v1/domains/overview", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [p["status"] for p in body["providers"]] == ["connected", "connected"]
    assert [d["name"] for d in body["domains"]] == ["acme.test"]
    domain = body["domains"][0]
    assert domain["zone"]["id"] == "z-acme"
    assert [m["domain_name"] for m in domain["mail"]] == ["acme.test"]
    assert domain["hostnames"][0]["service"] == {
        "name": "acme-web", "kind": "app", "project_slug": "site", "environment_slug": "production",
    }

    # Another team sees none of it.
    assert beta
    other = client.get("/api/v1/domains/overview", headers=_headers(client, "beta")).json()
    assert other["domains"] == []


def test_overview_degrades_per_provider(client, monkeypatch):
    acme = asyncio.run(_seed("acme"))
    asyncio.run(_own(acme))
    _fake_providers(monkeypatch, mail_down=True)

    body = client.get("/api/v1/domains/overview", headers=_headers(client, "acme")).json()
    assert [(p["name"], p["status"]) for p in body["providers"]] == [
        ("Cloudflare", "connected"), ("Mailcow", "degraded"),
    ]
    assert body["domains"][0]["zone"]["id"] == "z-acme"
    assert body["domains"][0]["mail"] == []
