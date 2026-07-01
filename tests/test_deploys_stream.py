"""Native Tetra deploy build-log SSE stream (mirrors the Coolify streamer)."""

import asyncio

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant
from app.models.deployment import STATUS_BUILDING, STATUS_ERROR, STATUS_READY, Deployment
from app.modules.auth.service import AuthService
from app.modules.deploys.service import stream_deploy_log_events


class _FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


def _drain(fetch) -> str:
    async def _collect() -> str:
        chunks: list[str] = []
        async for chunk in stream_deploy_log_events(
            fetch, _FakeRequest(), poll_interval=0.0, max_seconds=5.0
        ):
            chunks.append(chunk)
        return "".join(chunks)

    return asyncio.run(_collect())


# ── Pure generator ─────────────────────────────────────────────────────────


def test_stream_emits_status_logs_and_done_for_terminal_deployment():
    async def fetch():
        return (STATUS_READY, "→ cloning\n✓ built\n✓ live")

    text = _drain(fetch)
    assert "event: status" in text
    assert text.count("event: log") == 3
    assert "cloning" in text and "live" in text
    assert "event: done" in text


def test_stream_emits_error_when_deployment_missing():
    async def fetch():
        return None

    text = _drain(fetch)
    assert "event: error" in text
    assert "not found" in text.lower()


def test_stream_emits_only_new_lines_and_status_transitions_across_polls():
    sequence = [
        (STATUS_BUILDING, "→ cloning"),
        (STATUS_BUILDING, "→ cloning\n✓ built"),
        (STATUS_ERROR, "→ cloning\n✓ built\n✗ boom"),
    ]
    state = {"n": 0}

    async def fetch():
        index = min(state["n"], len(sequence) - 1)
        state["n"] += 1
        return sequence[index]

    text = _drain(fetch)
    # 3 distinct log lines, no duplicates across polls
    assert text.count("event: log") == 3
    # building → error = two status events
    assert text.count("event: status") == 2
    assert "event: done" in text
    assert "boom" in text


# ── Endpoint (tenant-scoped) ───────────────────────────────────────────────


async def _seed_tenant_with_deployment(*, slug: str, email: str, project: str) -> str:
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
                tenant_id=tenant.id,
                email=email,
                full_name="Owner",
                password_hash=auth.hash_password("stream-pass"),
                is_active=True,
            )
        )
        deployment = Deployment(
            tenant_id=tenant.id, project=project, status=STATUS_READY,
            log="→ cloning\n✓ built\n✓ live", domain=f"{project}.example.com",
        )
        session.add(deployment)
        await session.flush()
        return deployment.id


def _login(client, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "stream-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_stream_endpoint_returns_sse_for_own_deployment(client):
    deployment_id = asyncio.run(
        _seed_tenant_with_deployment(slug="strm", email="owner@strm.test", project="demo")
    )
    headers = _login(client, "owner@strm.test")
    response = client.get(f"/api/v1/deploys/{deployment_id}/logs/stream", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert response.text.count("event: log") == 3
    assert "event: done" in response.text


def test_stream_endpoint_denies_foreign_tenant_deployment(client):
    foreign_id = asyncio.run(
        _seed_tenant_with_deployment(slug="other", email="owner@other.test", project="secret")
    )
    asyncio.run(_seed_tenant_with_deployment(slug="mine", email="owner@mine.test", project="app"))
    headers = _login(client, "owner@mine.test")
    response = client.get(f"/api/v1/deploys/{foreign_id}/logs/stream", headers=headers)
    assert response.status_code == 404
