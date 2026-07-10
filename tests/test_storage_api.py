import asyncio

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_CLOUDFLARE, RESOURCE_TYPE_BUCKET
from app.modules.auth.service import AuthService


async def _seed() -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key="s_plan", name="S", max_apps=5, max_domains=0,
                    cpu_millicores=500, mem_mb=512, disk_mb=2048)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name="S Tenant", slug="st", status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(AdminUser(
            tenant_id=tenant.id, email="owner@s.test", full_name="S Owner",
            password_hash=auth.hash_password("s-password"), is_active=True,
        ))
        # A foreign bucket owned by nobody-in-this-tenant, to prove fail-closed delete.
        session.add(TenantResource(
            tenant_id="other-tenant", provider=PROVIDER_CLOUDFLARE,
            resource_type=RESOURCE_TYPE_BUCKET, external_id="foreign-bucket", display_name="foreign",
        ))
        return tenant.id


def _login(client) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": "owner@s.test", "password": "s-password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _configure_r2(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "cloudflare_api_token", "cf-token")
    monkeypatch.setattr(get_settings(), "cloudflare_account_id", "acct123")
    monkeypatch.setattr(get_settings(), "cloudflare_r2_permission_group_id", "")
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)


def test_provision_bucket_records_resource(client, monkeypatch):
    asyncio.run(_seed())
    _configure_r2(monkeypatch)

    created: list[str] = []

    async def fake_create(self, name):
        created.append(name)
        return {"name": name}

    monkeypatch.setattr("app.services.r2.R2Client.create_bucket", fake_create)
    headers = _login(client)

    r = client.post("/api/v1/storage/buckets", headers=headers, json={"name": "assets"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"].endswith("-assets")  # namespaced by tenant
    assert body["credentials_issued"] is False  # no permission group configured
    assert created == [body["name"]]

    listed = client.get("/api/v1/storage/buckets", headers=headers).json()
    assert any(b["name"] == body["name"] for b in listed)


def test_delete_is_tenant_scoped(client, monkeypatch):
    asyncio.run(_seed())
    _configure_r2(monkeypatch)

    async def fake_delete(self, name):
        return None

    monkeypatch.setattr("app.services.r2.R2Client.delete_bucket", fake_delete)
    headers = _login(client)

    denied = client.delete("/api/v1/storage/buckets/foreign-bucket", headers=headers)
    assert denied.status_code == 404


def test_status_reports_unconfigured(client, monkeypatch):
    asyncio.run(_seed())
    monkeypatch.setattr(get_settings(), "cloudflare_account_id", "")
    headers = _login(client)
    r = client.get("/api/v1/storage/status", headers=headers)
    assert r.status_code == 200
    assert r.json()["configured"] is False
