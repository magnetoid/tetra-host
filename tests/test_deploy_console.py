import asyncio
import json

from app.api.routes import _stream_deployment_logs
from app.db import session_scope
from app.models import AdminUser, Tenant, TenantResource
from app.models.tenant_resource import PROVIDER_COOLIFY, RESOURCE_TYPE_SITE
from app.modules.auth.service import AuthService
from app.services.coolify import (
    CoolifyDeployment,
    _extract_deployment_uuid,
    parse_deployment_log_lines,
)


# ── Pure helpers ──────────────────────────────────────────────────────────


def test_parse_log_lines_handles_json_array():
    raw = json.dumps(
        [
            {"output": "Building image", "type": "stdout", "timestamp": "t1"},
            {"output": "Pushed", "type": "stderr", "timestamp": "t2"},
        ]
    )
    lines = parse_deployment_log_lines(raw)
    assert [line["output"] for line in lines] == ["Building image", "Pushed"]
    assert lines[1]["type"] == "stderr"
    assert lines[0]["timestamp"] == "t1"


def test_parse_log_lines_handles_plain_string_and_empty():
    assert parse_deployment_log_lines("") == []
    assert parse_deployment_log_lines(None) == []
    lines = parse_deployment_log_lines("line one\nline two\n")
    assert [line["output"] for line in lines] == ["line one", "line two"]
    assert all(line["type"] == "stdout" for line in lines)


def test_parse_log_lines_handles_wrapped_object():
    raw = json.dumps({"logs": [{"output": "hi"}]})
    assert parse_deployment_log_lines(raw)[0]["output"] == "hi"


def test_extract_deployment_uuid_supports_both_shapes():
    assert _extract_deployment_uuid({"deployments": [{"deployment_uuid": "dep-a"}]}) == "dep-a"
    assert _extract_deployment_uuid({"deployment_uuid": "dep-b"}) == "dep-b"
    assert _extract_deployment_uuid({"message": "queued"}) == ""


# ── SSE generator ─────────────────────────────────────────────────────────


class _FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


class _SequenceClient:
    """Returns each provided deployment on successive get_deployment calls."""

    def __init__(self, deployments: list[CoolifyDeployment]) -> None:
        self._deployments = deployments
        self.calls = 0

    async def get_deployment(self, _deployment_id: str) -> CoolifyDeployment:
        index = min(self.calls, len(self._deployments) - 1)
        self.calls += 1
        return self._deployments[index]


def _drain(client, request) -> str:
    async def _collect() -> str:
        chunks: list[str] = []
        async for chunk in _stream_deployment_logs(
            client, "dep-1", request, poll_interval=0.0, max_seconds=5.0
        ):
            chunks.append(chunk)
        return "".join(chunks)

    return asyncio.run(_collect())


def test_stream_emits_status_logs_and_done_for_terminal_deployment():
    deployment = CoolifyDeployment(
        id="dep-1",
        status="finished",
        deployment_log=json.dumps([{"output": "Building"}, {"output": "Deployed"}]),
    )
    text = _drain(_SequenceClient([deployment]), _FakeRequest())
    assert "event: status" in text
    assert text.count("event: log") == 2
    assert "Building" in text and "Deployed" in text
    assert "event: done" in text


def test_stream_only_emits_new_lines_across_polls():
    building = CoolifyDeployment(
        id="dep-1", status="in_progress", deployment_log=json.dumps([{"output": "step 1"}])
    )
    finished = CoolifyDeployment(
        id="dep-1",
        status="finished",
        deployment_log=json.dumps([{"output": "step 1"}, {"output": "step 2"}]),
    )
    text = _drain(_SequenceClient([building, finished]), _FakeRequest())
    # "step 1" must appear exactly once even though it was present in both polls.
    assert text.count("step 1") == 1
    assert text.count("step 2") == 1
    # Two distinct statuses were observed.
    assert text.count("event: status") == 2


def test_stream_reports_missing_deployment():
    class _NoneClient:
        async def get_deployment(self, _deployment_id: str):
            return None

    text = _drain(_NoneClient(), _FakeRequest())
    assert "event: error" in text
    assert "not found" in text.lower()


# ── API endpoints ─────────────────────────────────────────────────────────


async def _seed_console_tenant() -> None:
    async with session_scope() as session:
        auth_service = AuthService(session)
        tenant = Tenant(name="Console Tenant", slug="console", is_active=True)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id,
                email="owner@console.test",
                full_name="Console Owner",
                password_hash=auth_service.hash_password("console-password"),
                is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id,
                provider=PROVIDER_COOLIFY,
                resource_type=RESOURCE_TYPE_SITE,
                external_id="app-console",
                display_name="Console App",
            )
        )


def _login(client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@console.test", "password": "console-password"},
    )
    assert response.status_code == 200
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_api_deploy_returns_deployment_id(client, monkeypatch):
    asyncio.run(_seed_console_tenant())

    async def fake_deploy_application(self, application_uuid, force=False, tag=""):
        return {"ok": True, "message": "Deployment queued.", "deployment_id": "dep-xyz"}

    monkeypatch.setattr("app.services.coolify.CoolifyClient.deploy_application", fake_deploy_application)

    token = _login(client)
    response = client.post("/api/v1/sites/app-console/deploy", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["deployment_id"] == "dep-xyz"


def test_api_deployment_detail_returns_parsed_log(client, monkeypatch):
    asyncio.run(_seed_console_tenant())

    async def fake_get_deployment(self, deployment_uuid):
        return CoolifyDeployment(
            id=deployment_uuid,
            status="finished",
            commit="abc123",
            branch="main",
            deployment_log=json.dumps([{"output": "hello world", "type": "stdout", "timestamp": "t1"}]),
        )

    monkeypatch.setattr("app.services.coolify.CoolifyClient.get_deployment", fake_get_deployment)

    token = _login(client)
    response = client.get("/api/v1/sites/app-console/deployments/dep-1", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "finished"
    assert body["commit"] == "abc123"
    assert body["log_lines"][0]["output"] == "hello world"


def test_api_deployment_detail_denies_other_tenant(client):
    asyncio.run(_seed_console_tenant())
    token = _login(client)
    response = client.get("/api/v1/sites/app-foreign/deployments/dep-1", headers=_auth(token))
    assert response.status_code == 403


def test_api_deployment_stream_denies_other_tenant(client):
    asyncio.run(_seed_console_tenant())
    token = _login(client)
    response = client.get(
        "/api/v1/sites/app-foreign/deployments/dep-1/logs/stream", headers=_auth(token)
    )
    assert response.status_code == 403


def test_api_deployment_stream_requires_auth(client):
    response = client.get("/api/v1/sites/app-console/deployments/dep-1/logs/stream")
    assert response.status_code == 401
