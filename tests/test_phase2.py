import asyncio
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.coolify import (
    CoolifyActionResult,
    CoolifyApplication,
    CoolifyClient,
    normalize_coolify_resource,
)


def login(client: TestClient):
    response = client.post(
        "/auth/login",
        data={"email": "admin@cloud-industry.com", "password": "change-me-now"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_health_exposes_plugin_registry_and_theme():
    with TestClient(app) as client:
        data = client.get('/health').json()
    assert data['theme'] == 'cloud-industry'
    assert 'sites' in data['plugins']
    assert 'mail' in data['plugins']


def test_coolify_resource_normalization_supports_common_shapes():
    raw = {
        'uuid': 'abc123',
        'name': 'Production API',
        'fqdn': 'https://api.example.com,https://www.api.example.com',
        'status': 'running',
        'git_repository': 'magnetoid/api',
        'environment_name': 'production',
        'updated_at': '2026-06-26T12:00:00Z',
    }
    app_item = normalize_coolify_resource(raw)
    assert isinstance(app_item, CoolifyApplication)
    assert app_item.id == 'abc123'
    assert app_item.primary_domain == 'api.example.com'
    assert app_item.status == 'running'
    assert app_item.repository == 'magnetoid/api'
    assert app_item.environment == 'production'


def test_sites_page_has_vercel_like_sections_when_logged_in():
    with TestClient(app) as client:
        login(client)
        html = client.get('/sites').text
    assert 'Projects' in html
    assert 'Search projects' in html
    assert 'Production' in html
    assert 'Deploy' in html


def test_dashboard_has_professional_paas_copy_when_logged_in():
    with TestClient(app) as client:
        login(client)
        html = client.get('/dashboard').text
    assert 'PaaS Overview' in html
    assert 'Coolify backend' in html
    assert 'Signed in as' in html


def test_list_applications_supports_multiple_coolify_payload_shapes():
    client = CoolifyClient(base_url='https://coolify.example.com', token='x')

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.content = b'{}'

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    payloads = [
        [{
            'uuid': 'a1',
            'name': 'API',
            'fqdn': 'api.example.com',
            'status': 'running',
        }],
        {'data': [{
            'uuid': 'b2',
            'name': 'Web',
            'domain': 'https://web.example.com',
            'state': 'exited',
        }]},
        {'applications': [{
            'id': 'c3',
            'project_name': 'Docs',
            'fqdn': 'docs.example.com',
            'status': 'healthy',
        }]},
    ]

    results = []
    for payload in payloads:
        async def fake_get(self, url, headers):
            return FakeResponse(payload)

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            get = fake_get

        import app.services.coolify as coolify_module
        original = coolify_module.httpx.AsyncClient
        coolify_module.httpx.AsyncClient = lambda timeout=20: FakeAsyncClient()
        try:
            items = asyncio.run(client.list_applications())
            results.append(items[0])
        finally:
            coolify_module.httpx.AsyncClient = original

    assert [r.id for r in results] == ['a1', 'b2', 'c3']
    assert [r.primary_domain for r in results] == ['api.example.com', 'web.example.com', 'docs.example.com']


def test_list_applications_falls_back_gracefully_when_coolify_unreachable():
    client = CoolifyClient(base_url='https://coolify.example.com', token='x')

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            raise httpx.ConnectError('boom')

    import app.services.coolify as coolify_module
    original = coolify_module.httpx.AsyncClient
    coolify_module.httpx.AsyncClient = lambda timeout=20: FakeAsyncClient()
    try:
        items = asyncio.run(client.list_applications())
    finally:
        coolify_module.httpx.AsyncClient = original

    assert len(items) >= 1
    assert all(isinstance(item, CoolifyApplication) for item in items)


def test_coolify_trigger_action_uses_go_helper_when_configured(tmp_path):
    helper = tmp_path / 'helper.sh'
    helper.write_text('#!/usr/bin/env bash\nprintf \'{"ok": true, "action": "deploy", "application_id": "app-1", "detail": "accepted"}\\n\'\n')
    helper.chmod(0o755)
    client = CoolifyClient(base_url='https://coolify.example.com', token='x', action_helper=str(helper))
    result = asyncio.run(client.trigger_action('app-1', 'deploy'))
    assert isinstance(result, CoolifyActionResult)
    assert result.ok is True
    assert result.source == 'go-helper'
