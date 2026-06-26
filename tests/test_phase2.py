from fastapi.testclient import TestClient

from app.main import app
from app.services.coolify import CoolifyApplication, normalize_coolify_resource


def test_health_exposes_plugin_registry_and_theme():
    client = TestClient(app)
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


def test_sites_page_has_vercel_like_sections():
    client = TestClient(app)
    html = client.get('/sites').text
    assert 'Projects' in html
    assert 'Search projects' in html
    assert 'Production' in html
    assert 'Deployments' in html


def test_dashboard_has_professional_paas_copy():
    client = TestClient(app)
    html = client.get('/dashboard').text
    assert 'PaaS Overview' in html
    assert 'Coolify backend' in html
    assert 'Customer tenants' in html
