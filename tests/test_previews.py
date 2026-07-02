"""Preview environments: branch push → ephemeral preview stack; branch delete → teardown."""

import asyncio
import json

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import AdminUser, Plan, PreviewEnv, Tenant
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService, preview_project_name
from app.services.docker_engine import DockerEngine, DockerEngineError
from app.services.github_webhook import sign


async def _seed(*, slug: str, email: str) -> str:
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
                password_hash=auth.hash_password("prev-pass"), is_active=True,
            )
        )
        return tenant.id


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "prev-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_hook(client, headers, *, project="blog", ref="main", previews=True) -> dict:
    r = client.post(
        "/api/v1/deploy-hooks", headers=headers,
        json={"project": project, "git_url": "https://github.com/x/y", "ref": ref,
              "previews": previews},
    )
    assert r.status_code == 200
    return r.json()


def _service(tenant_unused=None) -> DeploysService:
    service = DeploysService(request=object())
    service.actions_enabled = True
    service.base_domain = "apps.test"
    return service


async def _preview_rows() -> list[PreviewEnv]:
    async with session_scope() as session:
        return list((await session.scalars(select(PreviewEnv))).all())


# ── Naming ─────────────────────────────────────────────────────────────────


def test_preview_project_name_slugs_branch():
    assert preview_project_name("blog", "feat/login") == "blog-git-feat-login"
    assert preview_project_name("blog", "Feature/UP case") == "blog-git-feature-up-case"


# ── Service ────────────────────────────────────────────────────────────────


def test_deploy_preview_creates_env_and_deployment(client, monkeypatch):
    runs: list[dict] = []

    async def fake_run(self, deployment_id, tenant_id, **kwargs):
        runs.append(kwargs)

    monkeypatch.setattr(DeploysService, "_run_deploy", fake_run)

    async def go():
        tenant_id = await _seed(slug="pv", email="o@pv.test")
        service = _service()
        deployment_id, domain = await service.deploy_preview_for_tenant(
            tenant_id, git_url="https://github.com/x/y", branch="feat/login",
            project="blog", port=3000,
        )
        await asyncio.sleep(0)
        assert deployment_id and domain == "blog-git-feat-login.apps.test"
        # The build runs against the preview stack but inherits the parent app's env.
        assert runs[0]["project"] == "blog-git-feat-login"
        assert runs[0]["env_project"] == "blog"
        assert runs[0]["ref"] == "feat/login"
        rows = await _preview_rows()
        assert len(rows) == 1
        assert rows[0].branch == "feat/login" and rows[0].preview_project == "blog-git-feat-login"
        assert rows[0].last_deployment_id == deployment_id

    asyncio.run(go())


def test_second_push_same_branch_reuses_env(client, monkeypatch):
    async def fake_run(self, deployment_id, tenant_id, **kwargs):
        return None

    monkeypatch.setattr(DeploysService, "_run_deploy", fake_run)

    async def go():
        tenant_id = await _seed(slug="pw", email="o@pw.test")
        service = _service()
        first, _ = await service.deploy_preview_for_tenant(
            tenant_id, git_url="g", branch="dev", project="blog", port=3000
        )
        second, _ = await service.deploy_preview_for_tenant(
            tenant_id, git_url="g", branch="dev", project="blog", port=3000
        )
        assert first != second
        rows = await _preview_rows()
        assert len(rows) == 1 and rows[0].last_deployment_id == second

    asyncio.run(go())


def test_preview_cap_is_enforced(client, monkeypatch):
    async def fake_run(self, deployment_id, tenant_id, **kwargs):
        return None

    monkeypatch.setattr(DeploysService, "_run_deploy", fake_run)
    monkeypatch.setattr(get_settings(), "max_previews_per_project", 1)

    async def go():
        tenant_id = await _seed(slug="px", email="o@px.test")
        service = _service()
        await service.deploy_preview_for_tenant(
            tenant_id, git_url="g", branch="dev", project="blog", port=3000
        )
        try:
            await service.deploy_preview_for_tenant(
                tenant_id, git_url="g", branch="other", project="blog", port=3000
            )
            raise AssertionError("expected DockerEngineError")
        except DockerEngineError as exc:
            assert exc.code == 409

    asyncio.run(go())


def test_teardown_removes_stack_and_row(client, monkeypatch):
    async def fake_run(self, deployment_id, tenant_id, **kwargs):
        return None

    removed: list[str] = []

    async def fake_remove(self, project, *, volumes=False):
        removed.append(project)
        return {}

    monkeypatch.setattr(DeploysService, "_run_deploy", fake_run)
    monkeypatch.setattr(DockerEngine, "remove_stack", fake_remove)

    async def go():
        tenant_id = await _seed(slug="py", email="o@py.test")
        service = _service()
        await service.deploy_preview_for_tenant(
            tenant_id, git_url="g", branch="dev", project="blog", port=3000
        )
        assert await service.teardown_preview_for_branch(tenant_id, "blog", "dev") is True
        assert removed == ["blog-git-dev"]
        assert await _preview_rows() == []
        # Second teardown is a no-op.
        assert await service.teardown_preview_for_branch(tenant_id, "blog", "dev") is False

    asyncio.run(go())


# ── Webhook routing ────────────────────────────────────────────────────────


def _post_event(client, hook: dict, event: str, payload: dict):
    body = json.dumps(payload).encode()
    return client.post(
        f"/api/v1/webhooks/github/{hook['id']}",
        content=body,
        headers={"X-GitHub-Event": event, "X-Hub-Signature-256": sign(hook["secret"], body)},
    )


def test_branch_push_deploys_preview(client, monkeypatch):
    asyncio.run(_seed(slug="wb", email="o@wb.test"))
    headers = _login(client, "o@wb.test")
    hook = _create_hook(client, headers, project="blog", ref="main")

    calls: list[dict] = []

    async def fake_preview(self, tenant_id, **kwargs):
        calls.append(kwargs)
        return "dep-prev-1", "blog-git-dev.apps.test"

    monkeypatch.setattr(DeploysService, "deploy_preview_for_tenant", fake_preview)

    r = _post_event(client, hook, "push", {"ref": "refs/heads/dev"})
    assert r.status_code == 202
    body = r.json()
    assert body["preview"] is True and body["deployment_id"] == "dep-prev-1"
    assert body["domain"] == "blog-git-dev.apps.test"
    assert calls[0]["project"] == "blog" and calls[0]["branch"] == "dev"


def test_branch_push_with_previews_disabled_is_ignored(client, monkeypatch):
    asyncio.run(_seed(slug="wd", email="o@wd.test"))
    headers = _login(client, "o@wd.test")
    hook = _create_hook(client, headers, previews=False)

    async def fail_preview(self, *a, **k):
        raise AssertionError("preview must not run when previews are disabled")

    monkeypatch.setattr(DeploysService, "deploy_preview_for_tenant", fail_preview)

    r = _post_event(client, hook, "push", {"ref": "refs/heads/dev"})
    assert r.status_code == 200 and r.json()["ignored"] is True


def test_branch_delete_event_tears_down_preview(client, monkeypatch):
    asyncio.run(_seed(slug="we", email="o@we.test"))
    headers = _login(client, "o@we.test")
    hook = _create_hook(client, headers, project="blog", ref="main")

    calls: list[tuple] = []

    async def fake_teardown(self, tenant_id, project, branch):
        calls.append((project, branch))
        return True

    monkeypatch.setattr(DeploysService, "teardown_preview_for_branch", fake_teardown)

    r = _post_event(client, hook, "delete", {"ref": "dev", "ref_type": "branch"})
    assert r.status_code == 200 and r.json()["preview_removed"] is True
    assert calls == [("blog", "dev")]


def test_push_with_deleted_flag_tears_down_preview(client, monkeypatch):
    asyncio.run(_seed(slug="wf", email="o@wf.test"))
    headers = _login(client, "o@wf.test")
    hook = _create_hook(client, headers, project="blog", ref="main")

    calls: list[tuple] = []

    async def fake_teardown(self, tenant_id, project, branch):
        calls.append((project, branch))
        return True

    monkeypatch.setattr(DeploysService, "teardown_preview_for_branch", fake_teardown)

    r = _post_event(client, hook, "push", {"ref": "refs/heads/dev", "deleted": True})
    assert r.status_code == 200 and r.json()["preview_removed"] is True
    assert calls == [("blog", "dev")]


def test_tag_push_is_ignored(client):
    asyncio.run(_seed(slug="wg", email="o@wg.test"))
    headers = _login(client, "o@wg.test")
    hook = _create_hook(client, headers, project="blog", ref="main")
    r = _post_event(client, hook, "push", {"ref": "refs/tags/v1.0"})
    assert r.status_code == 200 and r.json()["ignored"] is True


# ── API (tenant-scoped) ────────────────────────────────────────────────────


async def _insert_preview(tenant_id: str, *, project="blog", branch="dev") -> str:
    async with session_scope() as session:
        preview = PreviewEnv(
            tenant_id=tenant_id, project=project, branch=branch,
            preview_project=preview_project_name(project, branch),
            domain=f"{preview_project_name(project, branch)}.apps.test",
        )
        session.add(preview)
        await session.flush()
        return preview.id


def test_list_and_delete_previews_are_tenant_scoped(client, monkeypatch):
    async def fake_remove(self, project, *, volumes=False):
        return {}

    monkeypatch.setattr(DockerEngine, "remove_stack", fake_remove)
    monkeypatch.setattr(get_settings(), "enable_provider_actions", True)

    tenant_a = asyncio.run(_seed(slug="pa", email="a@pa.test"))
    asyncio.run(_seed(slug="pb", email="b@pb.test"))
    headers_a = _login(client, "a@pa.test")
    headers_b = _login(client, "b@pb.test")
    preview_id = asyncio.run(_insert_preview(tenant_a))

    listed = client.get("/api/v1/previews", headers=headers_a).json()
    assert [p["id"] for p in listed] == [preview_id]
    assert listed[0]["branch"] == "dev" and listed[0]["domain"].endswith("apps.test")
    assert client.get("/api/v1/previews", headers=headers_b).json() == []

    # B cannot delete A's preview; A can.
    assert client.delete(f"/api/v1/previews/{preview_id}", headers=headers_b).status_code == 404
    assert client.delete(f"/api/v1/previews/{preview_id}", headers=headers_a).status_code == 200
    assert client.get("/api/v1/previews", headers=headers_a).json() == []
