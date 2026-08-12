"""Cross-tenant isolation regressions.

Two distinct bug classes, both reachable by any authenticated tenant admin:

1. **Second-order IDOR on Coolify deployment ids.** The project routes prove the
   caller owns the PARENT application, then hand the child `deployment_id`
   straight to Coolify. But Coolify's deployment endpoints are FLAT
   (`/api/v1/deployments/{uuid}`), not nested under the application — so the
   parent check constrains nothing and any tenant can read, stream or cancel any
   other tenant's deployment. Build logs routinely carry env vars and registry
   credentials.

2. **An unguarded platform-wide maintenance surface.** `/maintenance` runs
   `php artisan` over root SSH against the SHARED Coolify host. It is gated on
   `require_admin` (any authenticated tenant admin) rather than
   `require_platform_admin`, so one tenant can take every tenant offline.
"""

import asyncio
import re

import pytest

from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.admin import ROLE_OWNER
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.modules.auth.service import AuthService
from app.services.coolify import CoolifyDeployment

ATTACKER_APP = "app-attacker"
VICTIM_APP = "app-victim"
VICTIM_DEPLOYMENT = "dep-victim-secret"
ATTACKER_DEPLOYMENT = "dep-attacker"

# What the victim's build log would contain. If the attacker can read this, the
# leak is not theoretical.
VICTIM_LOG = '[{"output": "AWS_SECRET_ACCESS_KEY=victim-super-secret", "type": "stdout"}]'


async def _seed_two_tenants() -> None:
    """Attacker and victim tenants, each owning exactly one Coolify application."""
    async with session_scope() as session:
        auth = AuthService(session)
        for slug, email, app_id in (
            ("attacker", "attacker@x.test", ATTACKER_APP),
            ("victim", "victim@x.test", VICTIM_APP),
        ):
            tenant = Tenant(name=slug, slug=slug, status="active", is_platform_scope=False)
            session.add(tenant)
            await session.flush()
            session.add(
                AdminUser(
                    tenant_id=tenant.id,
                    email=email,
                    full_name=slug,
                    password_hash=auth.hash_password("tenant-password"),
                    is_active=True,
                    role=ROLE_OWNER,
                )
            )
            session.add(
                TenantResource(
                    tenant_id=tenant.id,
                    provider=PROVIDER_COOLIFY,
                    resource_type=RESOURCE_TYPE_SITE,
                    external_id=app_id,
                    display_name=app_id,
                )
            )


def _api_login(client, email: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "tenant-password"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture
def coolify_stub(monkeypatch):
    """Stub Coolify so deployment ids live in one FLAT namespace, as they really do."""
    deployments = {
        # "finished" (a terminal status) purely so the SSE test terminates instead of
        # polling for its 900s safety timeout. The leak is identical either way.
        VICTIM_DEPLOYMENT: CoolifyDeployment(
            id=VICTIM_DEPLOYMENT, status="finished", deployment_log=VICTIM_LOG
        ),
        ATTACKER_DEPLOYMENT: CoolifyDeployment(
            id=ATTACKER_DEPLOYMENT, status="finished", deployment_log="[]"
        ),
    }
    by_app = {
        ATTACKER_APP: [deployments[ATTACKER_DEPLOYMENT]],
        VICTIM_APP: [deployments[VICTIM_DEPLOYMENT]],
    }
    cancelled: list[str] = []

    async def fake_get_deployment(self, deployment_uuid):
        return deployments.get(deployment_uuid)

    async def fake_list_for_app(self, application_uuid):
        return by_app.get(application_uuid, [])

    async def fake_cancel(self, deployment_uuid):
        cancelled.append(deployment_uuid)
        return {"ok": True, "message": "cancelled"}

    monkeypatch.setattr("app.services.coolify.CoolifyClient.get_deployment", fake_get_deployment)
    monkeypatch.setattr(
        "app.services.coolify.CoolifyClient.list_deployments_for_application", fake_list_for_app
    )
    monkeypatch.setattr("app.services.coolify.CoolifyClient.cancel_deployment", fake_cancel)
    return cancelled


# ---------------------------------------------------------------------------
# 1. Coolify deployment IDOR
# ---------------------------------------------------------------------------


def test_tenant_cannot_read_another_tenants_deployment(client, coolify_stub):
    asyncio.run(_seed_two_tenants())
    headers = _api_login(client, "attacker@x.test")

    resp = client.get(
        f"/api/v1/projects/{ATTACKER_APP}/deployments/{VICTIM_DEPLOYMENT}", headers=headers
    )

    assert resp.status_code == 404, (
        "CROSS-TENANT READ: attacker read the victim's deployment through their own "
        f"application id (got {resp.status_code}: {resp.text[:400]})"
    )
    assert "victim-super-secret" not in resp.text


def test_tenant_can_still_read_its_own_deployment(client, coolify_stub):
    """The fix must not break the legitimate path."""
    asyncio.run(_seed_two_tenants())
    headers = _api_login(client, "attacker@x.test")

    resp = client.get(
        f"/api/v1/projects/{ATTACKER_APP}/deployments/{ATTACKER_DEPLOYMENT}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == ATTACKER_DEPLOYMENT


def test_tenant_cannot_cancel_another_tenants_deployment(client, coolify_stub):
    asyncio.run(_seed_two_tenants())
    headers = _api_login(client, "attacker@x.test")

    resp = client.post(
        f"/api/v1/projects/{ATTACKER_APP}/deployments/{VICTIM_DEPLOYMENT}/cancel", headers=headers
    )

    assert resp.status_code == 404, (
        f"CROSS-TENANT WRITE: attacker cancelled the victim's deploy (got {resp.status_code})"
    )
    assert VICTIM_DEPLOYMENT not in coolify_stub, (
        "CROSS-TENANT WRITE: the cancel reached Coolify for the victim's deployment"
    )


def test_tenant_cannot_stream_another_tenants_build_log(client, coolify_stub):
    asyncio.run(_seed_two_tenants())
    headers = _api_login(client, "attacker@x.test")

    resp = client.get(
        f"/api/v1/projects/{ATTACKER_APP}/deployments/{VICTIM_DEPLOYMENT}/logs/stream",
        headers=headers,
    )

    assert resp.status_code == 404, (
        f"CROSS-TENANT READ: attacker opened the victim's live build-log stream "
        f"(got {resp.status_code})"
    )
    assert "victim-super-secret" not in resp.text


# ---------------------------------------------------------------------------
# 2. Platform-wide maintenance surface
# ---------------------------------------------------------------------------


def _csrf(html: str) -> str:
    """Local copy of conftest's helper.

    Deliberately NOT imported from tests.conftest: importing that module by path
    re-executes its `get_settings.cache_clear()`, which breaks unrelated test files.
    """
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None, "no csrf token in page"
    return match.group(1)


def _html_login(client, email: str) -> None:
    page = client.get("/auth/login")
    resp = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "tenant-password",
            "csrf_token": _csrf(page.text),
            "next_url": "/dashboard",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text


def test_tenant_admin_cannot_open_platform_maintenance_page(client):
    asyncio.run(_seed_two_tenants())
    _html_login(client, "attacker@x.test")

    resp = client.get("/maintenance", follow_redirects=False)

    assert resp.status_code == 303, (
        "PRIVILEGE ESCALATION: a tenant admin can open the platform maintenance "
        f"console (got {resp.status_code})"
    )
    assert resp.headers.get("Location") == "/dashboard"


def test_tenant_admin_cannot_run_platform_maintenance_command(client, monkeypatch):
    """The decisive assertion: the artisan runner must never be reached."""
    asyncio.run(_seed_two_tenants())
    _html_login(client, "attacker@x.test")

    invoked: list[str] = []

    async def fake_run_artisan(command: str) -> tuple[int, str]:
        invoked.append(command)
        return 0, "ok"

    monkeypatch.setattr("app.modules.maintenance.routes._run_artisan", fake_run_artisan)

    page = client.get("/dashboard")
    resp = client.post(
        "/maintenance/run",
        data={"command": "down", "csrf_token": _csrf(page.text)},
        follow_redirects=False,
    )

    assert invoked == [], (
        "PLATFORM DoS: a tenant admin executed 'artisan down' on the shared Coolify "
        "host, taking every tenant offline"
    )
    assert resp.status_code == 303
    assert resp.headers.get("Location") == "/dashboard"
