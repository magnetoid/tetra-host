"""GitHub push-to-deploy webhooks: hook CRUD, HMAC-authed receiver, redeploy guard."""

import asyncio
import json

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService
from app.services.docker_engine import DockerEngineError
from app.services.github_webhook import sign


async def _seed(*, slug: str, email: str, app_project: str | None = None) -> str:
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
                password_hash=auth.hash_password("hook-pass"), is_active=True,
            )
        )
        if app_project:
            session.add(
                TenantResource(
                    tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                    resource_type=RESOURCE_TYPE_APP, external_id=app_project, display_name=app_project,
                )
            )
        return tenant.id


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "hook-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_hook(client, headers, *, project="blog", git_url="https://github.com/x/y", ref="main") -> dict:
    r = client.post(
        "/api/v1/deploy-hooks", headers=headers,
        json={"project": project, "git_url": git_url, "ref": ref},
    )
    assert r.status_code == 200
    return r.json()


# ── Management (authed, tenant-scoped) ─────────────────────────────────────


def test_create_lists_and_deletes_hook(client):
    asyncio.run(_seed(slug="hk", email="owner@hk.test"))
    headers = _login(client, "owner@hk.test")
    created = _create_hook(client, headers)
    assert created["url"].endswith(f"/api/v1/webhooks/github/{created['id']}")
    assert created["secret"]  # shown once

    hooks = client.get("/api/v1/deploy-hooks", headers=headers).json()
    assert [h["id"] for h in hooks] == [created["id"]]
    assert "secret" not in hooks[0]  # never listed

    assert client.delete(f"/api/v1/deploy-hooks/{created['id']}", headers=headers).status_code == 200
    assert client.get("/api/v1/deploy-hooks", headers=headers).json() == []


def test_hooks_are_tenant_scoped(client):
    asyncio.run(_seed(slug="ha", email="a@ha.test"))
    asyncio.run(_seed(slug="hb", email="b@hb.test"))
    headers_a = _login(client, "a@ha.test")
    headers_b = _login(client, "b@hb.test")
    created = _create_hook(client, headers_a)
    assert client.get("/api/v1/deploy-hooks", headers=headers_b).json() == []
    # B cannot delete A's hook
    assert client.delete(f"/api/v1/deploy-hooks/{created['id']}", headers=headers_b).status_code == 404


# ── Webhook receiver (HMAC-authenticated, unauthenticated session) ─────────


def test_unknown_hook_returns_404(client):
    r = client.post("/api/v1/webhooks/github/nope", content=b"{}")
    assert r.status_code == 404


def test_bad_signature_rejected(client):
    asyncio.run(_seed(slug="sig", email="owner@sig.test", app_project="blog"))
    headers = _login(client, "owner@sig.test")
    created = _create_hook(client, headers)
    url = f"/api/v1/webhooks/github/{created['id']}"
    body = b'{"ref":"refs/heads/main"}'
    # Missing signature
    assert client.post(url, content=body, headers={"X-GitHub-Event": "push"}).status_code == 401
    # Wrong signature
    assert client.post(
        url, content=body,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=deadbeef"},
    ).status_code == 401


def test_ping_event_pongs(client):
    asyncio.run(_seed(slug="png", email="owner@png.test", app_project="blog"))
    headers = _login(client, "owner@png.test")
    created = _create_hook(client, headers)
    body = b'{"zen":"hi"}'
    sig = sign(created["secret"], body)
    r = client.post(
        f"/api/v1/webhooks/github/{created['id']}",
        content=body, headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
    )
    assert r.status_code == 200 and r.json()["pong"] is True


def test_push_to_matching_branch_triggers_redeploy(client, monkeypatch):
    asyncio.run(_seed(slug="psh", email="owner@psh.test", app_project="blog"))
    headers = _login(client, "owner@psh.test")
    created = _create_hook(client, headers, project="blog", ref="main")

    calls: list[dict] = []

    async def fake_redeploy(self, tenant_id, **kwargs):
        calls.append({"tenant_id": tenant_id, **kwargs})
        return "dep-redeploy-1"

    monkeypatch.setattr(DeploysService, "redeploy_for_tenant", fake_redeploy)

    body = json.dumps({"ref": "refs/heads/main"}).encode()
    sig = sign(created["secret"], body)
    r = client.post(
        f"/api/v1/webhooks/github/{created['id']}",
        content=body, headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
    )
    assert r.status_code == 202
    assert r.json()["deployment_id"] == "dep-redeploy-1"
    assert calls and calls[0]["project"] == "blog" and calls[0]["ref"] == "main"


def test_push_to_other_branch_is_ignored(client, monkeypatch):
    asyncio.run(_seed(slug="oth", email="owner@oth.test", app_project="blog"))
    headers = _login(client, "owner@oth.test")
    created = _create_hook(client, headers, ref="main")

    async def fail_redeploy(self, *a, **k):  # must NOT be called
        raise AssertionError("redeploy should not run for a non-matching branch")

    monkeypatch.setattr(DeploysService, "redeploy_for_tenant", fail_redeploy)

    body = json.dumps({"ref": "refs/heads/dev"}).encode()
    sig = sign(created["secret"], body)
    r = client.post(
        f"/api/v1/webhooks/github/{created['id']}",
        content=body, headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
    )
    assert r.status_code == 200 and r.json()["ignored"] is True


# ── Redeploy guard (no quota bypass) ───────────────────────────────────────


def test_redeploy_requires_existing_app(client):
    async def go():
        tenant_id = await _seed(slug="ng", email="owner@ng.test")  # no app resource
        service = DeploysService(request=object())
        service.actions_enabled = True  # bypass the ENABLE_PROVIDER_ACTIONS gate for the guard path
        try:
            await service.redeploy_for_tenant(
                tenant_id, git_url="https://github.com/x/y", ref="main", project="ghost", port=3000
            )
            raise AssertionError("expected DockerEngineError")
        except DockerEngineError as exc:
            assert exc.code == 404

    asyncio.run(go())
