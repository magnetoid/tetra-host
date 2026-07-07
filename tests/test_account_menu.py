"""Slice A — the upper-right account dropdown + role exposure + Account page (panel).

The panel never surfaced the admin's role to templates, so it couldn't gate a
Super Admin link. These tests pin: role reaches the template, platform-admin-only
nav/menu items are hidden from owners, and the new /account page renders.
"""

import re

from app.db import session_scope
from app.models import AdminUser, Tenant
from app.models.admin import ROLE_OWNER
from app.modules.auth.service import AuthService


def _extract_csrf(html: str) -> str:
    # NB: a module-level `from tests.conftest import …` duplicates conftest as a
    # separate module and corrupts shared DB/limiter state (see test_html_isolation).
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


async def _seed_owner(slug: str, email: str, password: str = "owner-pass") -> None:
    from sqlalchemy import select

    async with session_scope() as session:
        if await session.scalar(select(Tenant).where(Tenant.slug == slug)):
            return
        auth = AuthService(session)
        tenant = Tenant(name=f"Tenant {slug}", slug=slug, status="active", is_platform_scope=False)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=email, full_name=f"Owner {slug}", role=ROLE_OWNER,
                password_hash=auth.hash_password(password), is_active=True,
            )
        )


def _login(client, email: str, password: str):
    csrf = _extract_csrf(client.get("/auth/login").text)
    resp = client.post(
        "/auth/login",
        data={"email": email, "password": password, "csrf_token": csrf, "next_url": "/dashboard"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client


# ── Role reaches the header menu ────────────────────────────────────────────


def test_platform_admin_sees_super_admin_link(authenticated_client):
    html = authenticated_client.get("/dashboard").text
    assert "Super Admin" in html
    assert 'href="/admin"' in html  # the platform-admin destination is present


def test_owner_does_not_see_admin_anywhere(client):
    import asyncio

    asyncio.run(_seed_owner("ownermenu", "owner@ownermenu.test"))
    _login(client, "owner@ownermenu.test", "owner-pass")
    html = client.get("/dashboard").text
    # No Super Admin dropdown item AND no sidebar Admin link for a non-platform admin.
    assert "Super Admin" not in html
    assert 'href="/admin"' not in html
    # …but the account menu itself is present.
    assert 'href="/account"' in html
    assert "owner@ownermenu.test" in html


def test_account_menu_has_account_and_logout(authenticated_client):
    html = authenticated_client.get("/dashboard").text
    assert 'href="/account"' in html
    assert 'action="/auth/logout"' in html  # CSRF logout form preserved


# ── The account page ────────────────────────────────────────────────────────


def test_account_page_renders_profile(authenticated_client):
    resp = authenticated_client.get("/account")
    assert resp.status_code == 200
    import os

    assert os.environ["ADMIN_BOOTSTRAP_EMAIL"] in resp.text


def test_account_page_requires_auth(client):
    resp = client.get("/account", follow_redirects=False)
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]


# ── Theme toggle mechanism present in the shell ─────────────────────────────


def test_theme_toggle_control_rendered(authenticated_client):
    html = authenticated_client.get("/dashboard").text
    # The no-flash theme script + a toggle control are wired into the shell.
    assert re.search(r"data-theme|localStorage\.getItem\('tetra-theme'\)|tetra-theme", html)
