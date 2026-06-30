"""
tests/test_html_isolation.py

TDD tests for HTML route tenant-isolation bypasses (Task 2.1-HTML).

Covers:
  - Dashboard GET /dashboard: unfiltered vs tenant-scoped provider calls
  - DNS mutations POST /dns/records/create, /dns/records/{id}/edit, /dns/records/{id}/delete:
    cross-tenant zone mutations are denied, own-zone mutations are allowed.

NOTE on asyncio.run() + client fixture
---------------------------------------
SQLite / aiosqlite keeps background threads alive for the duration of the event
loop.  When `asyncio.run()` is used INSIDE a test body that also uses the `client`
fixture (which runs the app via TestClient in its own greenlet context), the two
event loops share a single module-level engine.  If multiple tests in the same
file each call `asyncio.run()` with the same SQLite file, the background thread
from a prior run may hold the file open when the next test's `_isolate_test_db`
fixture tries to delete and recreate it.

Mitigation strategy used here:
  1. Each test's seed helper is idempotent (skips if tenant already exists).
  2. DNS mutation tests each use a unique tenant slug so they never collide.
  3. Dashboard tests use monkeypatch-only fakes — no asyncio.run() needed
     for test_dashboard_non_platform_admin, or it uses asyncio.run() only once.

IMPORTANT: do NOT import ``from tests.conftest import …`` at module level in
this file — doing so re-executes conftest's ``get_settings.cache_clear()`` during
pytest collection, causing ``create_app()``'s closure to hold a *stale* instance
while ``get_settings()`` returns a *new* one, making patches invisible to routes.
"""

import asyncio
import re

import pytest

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import (
    PROVIDER_CLOUDFLARE,
    RESOURCE_TYPE_DNS_ZONE,
)
from app.modules.auth.service import AuthService


def extract_csrf_token(html: str) -> str:
    """Extract the CSRF token from an HTML page (mirrors conftest helper)."""
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


# ---------------------------------------------------------------------------
# Shared seed helpers
# ---------------------------------------------------------------------------


async def _seed_tenant(slug: str, email: str, password: str, zone_id: str) -> None:
    """Generic idempotent seed: create a non-platform tenant with one DNS zone.

    If the tenant slug already exists (asyncio event-loop isolation edge case),
    we skip the insert so subsequent tests in the same DB file don't fail.
    """
    from sqlalchemy import select as _select

    async with session_scope() as session:
        existing = await session.scalar(_select(Tenant).where(Tenant.slug == slug))
        if existing is not None:
            return
        auth_service = AuthService(session)
        tenant = Tenant(name=f"Tenant {slug}", slug=slug, status="active", is_platform_scope=False)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email=email,
                full_name=f"Admin {slug}",
                password_hash=auth_service.hash_password(password),
                is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_CLOUDFLARE,
                resource_type=RESOURCE_TYPE_DNS_ZONE,
                external_id=zone_id,
                display_name=f"{zone_id}.test",
            )
        )


async def _seed_cust_tenant() -> None:
    """Seed the dashboard test tenant (slug='cust')."""
    await _seed_tenant("cust", "cust@example.test", "cust-pass", "zone-mapped")


def _login(client, email: str, password: str):
    """Login via the HTML form and return client (session cookie set)."""
    login_page = client.get("/auth/login")
    csrf = extract_csrf_token(login_page.text)
    resp = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": password,
            "csrf_token": csrf,
            "next_url": "/dashboard",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client


def _login_cust(client):
    return _login(client, "cust@example.test", "cust-pass")


def _get_csrf(client):
    """Fetch CSRF token, falling back to login page if DNS form is hidden."""
    resp = client.get("/dns")
    if 'name="csrf_token"' not in resp.text:
        resp = client.get("/auth/login")
    return extract_csrf_token(resp.text)


# ---------------------------------------------------------------------------
# provider_actions_enabled fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def provider_actions_enabled():
    """Enable provider actions for the duration of the test.

    DNS mutation routes gate on ``request.state.settings.enable_provider_actions``.
    The middleware injects the Settings singleton (captured once by ``create_app()``)
    into every ``request.state``.  ``get_settings()`` returns that same singleton
    (lru-cached), so patching it here is visible inside the request handler.

    IMPORTANT: do NOT import ``from tests.conftest import …`` at module level in
    this file — doing so re-executes conftest's ``get_settings.cache_clear()`` during
    pytest collection, causing ``create_app()``'s closure to hold a *stale* instance
    while ``get_settings()`` returns a *new* one, making patches invisible to routes.
    """
    from unittest.mock import patch

    with patch.object(get_settings(), "enable_provider_actions", True):
        yield


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------


def test_dashboard_platform_admin_sees_all(authenticated_client, monkeypatch):
    """Platform-scope bootstrap admin should see all (unfiltered) provider data."""

    async def fake_list_sites(self, session, tenant_id, **kw):
        from unittest.mock import MagicMock
        site = MagicMock()
        site.name = "platform-site"
        site.status = "running"
        return [site]

    async def fake_mail_load(self, session, tenant_id, **kw):
        from unittest.mock import MagicMock
        domain = MagicMock()
        domain.domain_name = "platform-domain.test"
        return [domain], []

    async def fake_dns_load(self, session, tenant_id, **kw):
        from unittest.mock import MagicMock
        zone = MagicMock()
        zone.id = "zone-platform"
        zone.name = "platform.test"
        return [zone], [], "zone-platform"

    monkeypatch.setattr(
        "app.modules.projects.service.ProjectsService.list_sites_for_tenant",
        fake_list_sites,
    )
    monkeypatch.setattr(
        "app.modules.mail.service.MailService.load_for_tenant",
        fake_mail_load,
    )
    monkeypatch.setattr(
        "app.modules.dns.service.DnsService.load_for_tenant",
        fake_dns_load,
    )

    resp = authenticated_client.get("/dashboard")
    assert resp.status_code == 200
    assert "platform-site" in resp.text
    assert "platform-domain.test" in resp.text
    assert "platform.test" in resp.text


def test_dashboard_non_platform_admin_sees_only_own_resources(client, monkeypatch):
    """A non-platform tenant admin with no mapped resources sees zero counts."""
    asyncio.run(_seed_cust_tenant())

    call_log: list[str] = []

    async def fake_list_sites_for_tenant(self, session, tenant_id, **kw):
        call_log.append(f"sites:{tenant_id}")
        return []

    async def fake_mail_load_for_tenant(self, session, tenant_id, **kw):
        call_log.append(f"mail:{tenant_id}")
        return [], []

    async def fake_dns_load_for_tenant(self, session, tenant_id, **kw):
        call_log.append(f"dns:{tenant_id}")
        return [], [], ""

    monkeypatch.setattr(
        "app.modules.projects.service.ProjectsService.list_sites_for_tenant",
        fake_list_sites_for_tenant,
    )
    monkeypatch.setattr(
        "app.modules.mail.service.MailService.load_for_tenant",
        fake_mail_load_for_tenant,
    )
    monkeypatch.setattr(
        "app.modules.dns.service.DnsService.load_for_tenant",
        fake_dns_load_for_tenant,
    )

    _login_cust(client)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    # The tenant-scoped methods were called (not the unfiltered ones)
    assert any("sites:" in entry for entry in call_log)
    assert any("dns:" in entry for entry in call_log)


# ---------------------------------------------------------------------------
# DNS HTML mutation tests — each uses a unique slug to avoid cross-test DB collision
# ---------------------------------------------------------------------------


def test_html_dns_create_foreign_zone_denied(client, monkeypatch, provider_actions_enabled):
    """POST /dns/records/create with a foreign zone_id must be denied (provider not called)."""
    asyncio.run(_seed_tenant("t-create-deny", "create-deny@example.test", "password1", "zone-own-1"))

    created: list[str] = []

    async def fake_create(self, zone_id, record_type, name, content, ttl=1, proxied=False, priority=None):
        created.append(zone_id)
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.create_dns_record", fake_create)

    _login(client, "create-deny@example.test", "password1")
    csrf = _get_csrf(client)

    resp = client.post(
        "/dns/records/create",
        data={
            "zone_id": "zone-foreign",
            "record_type": "A",
            "name": "sub.foreign.test",
            "content": "1.2.3.4",
            "ttl": "1",
            "proxied": "false",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "zone-foreign" in location
    assert "error=" in location
    assert created == [], "Provider must NOT be called for foreign zone"


def test_html_dns_create_own_zone_allowed(client, monkeypatch, provider_actions_enabled):
    """POST /dns/records/create with the tenant's mapped zone_id must succeed."""
    asyncio.run(_seed_tenant("t-create-allow", "create-allow@example.test", "password2", "zone-own-2"))

    created: list[str] = []

    async def fake_create(self, zone_id, record_type, name, content, ttl=1, proxied=False, priority=None):
        created.append(zone_id)
        return {"id": "rec-new", "type": record_type, "name": name}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.create_dns_record", fake_create)

    _login(client, "create-allow@example.test", "password2")
    csrf = _get_csrf(client)

    resp = client.post(
        "/dns/records/create",
        data={
            "zone_id": "zone-own-2",
            "record_type": "A",
            "name": "sub.own.test",
            "content": "1.2.3.4",
            "ttl": "1",
            "proxied": "false",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "zone-own-2" in location
    assert "success=" in location
    assert created == ["zone-own-2"], "Provider must be called exactly once for own zone"


def test_html_dns_edit_foreign_zone_denied(client, monkeypatch, provider_actions_enabled):
    """POST /dns/records/{id}/edit with foreign zone_id must be denied."""
    asyncio.run(_seed_tenant("t-edit-deny", "edit-deny@example.test", "password3", "zone-own-3"))

    updated: list[str] = []

    async def fake_update(self, zone_id, record_id, record_type, name, content, ttl=1, proxied=False, priority=None):
        updated.append(zone_id)
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.update_dns_record", fake_update)

    _login(client, "edit-deny@example.test", "password3")
    csrf = _get_csrf(client)

    resp = client.post(
        "/dns/records/rec-1/edit",
        data={
            "zone_id": "zone-foreign",
            "record_type": "A",
            "name": "sub.foreign.test",
            "content": "9.9.9.9",
            "ttl": "1",
            "proxied": "false",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "zone-foreign" in location
    assert "error=" in location
    assert updated == [], "Provider must NOT be called for foreign zone"


def test_html_dns_delete_foreign_zone_denied(client, monkeypatch, provider_actions_enabled):
    """POST /dns/records/{id}/delete with foreign zone_id must be denied."""
    asyncio.run(_seed_tenant("t-delete-deny", "delete-deny@example.test", "password4", "zone-own-4"))

    deleted: list[tuple[str, str]] = []

    async def fake_delete(self, zone_id, record_id):
        deleted.append((zone_id, record_id))
        return {"ok": True}

    monkeypatch.setattr("app.services.cloudflare.CloudflareClient.delete_dns_record", fake_delete)

    _login(client, "delete-deny@example.test", "password4")
    csrf = _get_csrf(client)

    resp = client.post(
        "/dns/records/rec-1/delete",
        data={
            "zone_id": "zone-foreign",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "zone-foreign" in location
    assert "error=" in location
    assert deleted == [], "Provider must NOT be called for foreign zone"
