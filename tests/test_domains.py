"""Custom domains: claim → TXT verify → edge ask + routing. Tenant-scoped."""

import asyncio

import yaml

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.modules.domains.service import DomainsService
from app.services.edge import apply_edge


async def _seed(*, slug: str, email: str, app: str = "blog") -> None:
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
                tenant_id=tenant.id, email=email, full_name="Owner",
                password_hash=auth.hash_password("dom-pass"), is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                resource_type=RESOURCE_TYPE_APP, external_id=app, display_name=app,
            )
        )


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "dom-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _fake_resolver(records: list[str]):
    async def resolve(_name: str) -> list[str]:
        return records

    return resolve


# ── Validation ─────────────────────────────────────────────────────────────


def test_hostname_normalization_and_rejection(monkeypatch):
    monkeypatch.setattr(get_settings(), "apps_base_domain", "apps.test")
    assert DomainsService.normalize_hostname("WWW.Example.COM.") == "www.example.com"
    for bad in ["", "nodots", "-bad.example.com", "http://x.com", "a b.com"]:
        try:
            DomainsService.normalize_hostname(bad)
            raise AssertionError(f"expected ValueError for {bad!r}")
        except ValueError:
            pass
    # our own base domain is off-limits
    try:
        DomainsService.normalize_hostname("foo.apps.test")
        raise AssertionError("expected ValueError for base-domain subdomain")
    except ValueError:
        pass


# ── Claim / verify / ask (API) ─────────────────────────────────────────────


def test_claim_verify_and_edge_ask_flow(client, monkeypatch):
    asyncio.run(_seed(slug="dm", email="owner@dm.test"))
    headers = _login(client, "owner@dm.test")

    r = client.post("/api/v1/domains", headers=headers, json={"project": "blog", "hostname": "www.example.com"})
    assert r.status_code == 200
    domain = r.json()
    assert domain["status"] == "pending"
    assert domain["txt_name"] == "_tetra-challenge.www.example.com"
    assert domain["txt_value"]

    # ask says no while pending
    assert client.get("/api/v1/edge/ask", params={"domain": "www.example.com"}).status_code == 404

    # wrong TXT → 409 with instructions
    monkeypatch.setattr(
        "app.modules.domains.service._dig_txt_resolver", _fake_resolver(["nope"])
    )
    r = client.post(f"/api/v1/domains/{domain['id']}/verify", headers=headers)
    assert r.status_code == 409

    # correct TXT → verified
    monkeypatch.setattr(
        "app.modules.domains.service._dig_txt_resolver", _fake_resolver([domain["txt_value"]])
    )
    r = client.post(f"/api/v1/domains/{domain['id']}/verify", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "verified"

    # ask now answers 200 (Caddy may mint a cert)
    assert client.get("/api/v1/edge/ask", params={"domain": "www.example.com"}).status_code == 200
    # unknown domains stay 404
    assert client.get("/api/v1/edge/ask", params={"domain": "evil.example.net"}).status_code == 404


def test_duplicate_claim_rejected_across_tenants(client):
    asyncio.run(_seed(slug="da", email="a@da.test"))
    asyncio.run(_seed(slug="db", email="b@db.test"))
    headers_a = _login(client, "a@da.test")
    headers_b = _login(client, "b@db.test")
    assert (
        client.post("/api/v1/domains", headers=headers_a, json={"project": "blog", "hostname": "shop.example.com"})
        .status_code == 200
    )
    r = client.post("/api/v1/domains", headers=headers_b, json={"project": "blog", "hostname": "shop.example.com"})
    assert r.status_code == 409


def test_domains_are_tenant_scoped(client):
    asyncio.run(_seed(slug="ds", email="a@ds.test"))
    asyncio.run(_seed(slug="dt", email="b@dt.test"))
    headers_a = _login(client, "a@ds.test")
    headers_b = _login(client, "b@dt.test")
    created = client.post(
        "/api/v1/domains", headers=headers_a, json={"project": "blog", "hostname": "a-only.example.com"}
    ).json()
    assert client.get("/api/v1/domains", headers=headers_b).json() == []
    assert client.delete(f"/api/v1/domains/{created['id']}", headers=headers_b).status_code == 404
    assert client.post(f"/api/v1/domains/{created['id']}/verify", headers=headers_b).status_code == 404


def test_claim_requires_owned_app(client):
    asyncio.run(_seed(slug="dn", email="owner@dn.test", app="mine"))
    headers = _login(client, "owner@dn.test")
    r = client.post("/api/v1/domains", headers=headers, json={"project": "not-mine", "hostname": "x.example.com"})
    assert r.status_code == 403


def test_invalid_hostname_422(client):
    asyncio.run(_seed(slug="dv", email="owner@dv.test"))
    headers = _login(client, "owner@dv.test")
    r = client.post("/api/v1/domains", headers=headers, json={"project": "blog", "hostname": "not a domain"})
    assert r.status_code == 422


# ── Edge routing label ─────────────────────────────────────────────────────


def test_apply_edge_adds_custom_hosts_to_site_addresses(monkeypatch):
    monkeypatch.setattr(get_settings(), "edge_network", "tetra-edge")
    monkeypatch.setattr(get_settings(), "apps_base_domain", "apps.test")
    compose = yaml.safe_dump({"services": {"app": {"image": "img", "expose": ["3000"]}}})
    out = yaml.safe_load(
        apply_edge(compose, project="blog", port="3000", extra_hosts=["www.example.com"])
    )
    label = out["services"]["app"]["labels"]["tetra"]
    assert label == "http://blog.apps.test, http://www.example.com"
