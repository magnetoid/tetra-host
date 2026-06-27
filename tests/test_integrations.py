import asyncio

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.cloudflare import CloudflareClient, CloudflareZone
from app.services.mailcow import MailcowClient, MailcowDomain


def test_mail_page_renders_domains_section():
    client = TestClient(app)
    html = client.get('/mail').text
    assert 'Mailcow domains' in html
    assert 'imbaproduction.com' in html


def test_dns_page_renders_zones_section():
    client = TestClient(app)
    html = client.get('/dns').text
    assert 'Cloudflare zones' in html
    assert 'montenegro-experience.me' in html


def test_mailcow_list_domains_supports_common_payload_shapes():
    client = MailcowClient(base_url='https://mail.example.com', api_key='x')

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    payloads = [
        [{'domain_name': 'alpha.com', 'active': '1', 'mboxes_in_domain': 3, 'aliases_in_domain': 5}],
        {'data': [{'domain_name': 'beta.com', 'active': '0', 'maxquota_for_domain': '10 GiB'}]},
        {'domains': [{'domain': 'gamma.com', 'description': 'Gamma'}]},
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

        import app.services.mailcow as module
        original = module.httpx.AsyncClient
        module.httpx.AsyncClient = lambda timeout=20: FakeAsyncClient()
        try:
            items = asyncio.run(client.list_domains())
            results.append(items[0])
        finally:
            module.httpx.AsyncClient = original

    assert all(isinstance(item, MailcowDomain) for item in results)
    assert [item.domain for item in results] == ['alpha.com', 'beta.com', 'gamma.com']


def test_cloudflare_list_zones_supports_result_payload():
    client = CloudflareClient(api_token='x')

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'success': True,
                'result': [
                    {
                        'id': 'zone1',
                        'name': 'example.com',
                        'status': 'active',
                        'plan': {'name': 'Pro'},
                        'name_servers': ['a.ns.cloudflare.com', 'b.ns.cloudflare.com'],
                    }
                ],
            }

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    import app.services.cloudflare as module
    original = module.httpx.AsyncClient
    module.httpx.AsyncClient = lambda timeout=20: FakeAsyncClient()
    try:
        items = asyncio.run(client.list_zones())
    finally:
        module.httpx.AsyncClient = original

    assert len(items) == 1
    assert isinstance(items[0], CloudflareZone)
    assert items[0].name == 'example.com'
    assert items[0].plan == 'Pro'


def test_provider_integrations_fall_back_gracefully_on_http_errors():
    mail_client = MailcowClient(base_url='https://mail.example.com', api_key='x')
    cf_client = CloudflareClient(api_token='x')

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            raise httpx.ConnectError('boom')

    import app.services.mailcow as mail_module
    import app.services.cloudflare as cf_module
    orig_mail = mail_module.httpx.AsyncClient
    orig_cf = cf_module.httpx.AsyncClient
    mail_module.httpx.AsyncClient = lambda timeout=20: FakeAsyncClient()
    cf_module.httpx.AsyncClient = lambda timeout=20: FakeAsyncClient()
    try:
        mail_items = asyncio.run(mail_client.list_domains())
        cf_items = asyncio.run(cf_client.list_zones())
    finally:
        mail_module.httpx.AsyncClient = orig_mail
        cf_module.httpx.AsyncClient = orig_cf

    assert len(mail_items) >= 1
    assert len(cf_items) >= 1
