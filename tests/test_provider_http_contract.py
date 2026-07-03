"""The provider HTTP contract: request_json NEVER leaks raw transport/parse errors.

Callers' best-effort paths catch ProviderAPIError only — a raw httpx.ConnectTimeout
or json.JSONDecodeError escaping request_json breaks every such path (this orphaned
mail domains before the fix: crash after provider-create rolled back ownership).
"""

import asyncio

import httpx
import pytest

from app.config import Settings
from app.services.http import ProviderAPIError, request_json


def _call(handler, **kwargs):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return asyncio.run(
        request_json(client, service="Test", method="GET", url="https://x.test/y", **kwargs)
    )


def test_connect_timeout_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    with pytest.raises(ProviderAPIError):
        _call(handler, max_attempts=2)


def test_pool_timeout_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.PoolTimeout("exhausted")

    with pytest.raises(ProviderAPIError):
        _call(handler, max_attempts=1)


def test_invalid_json_body_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>proxy error page</html>")

    with pytest.raises(ProviderAPIError) as err:
        _call(handler)
    assert "invalid JSON" in str(err.value)


def test_transport_errors_are_retried_then_wrapped():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadError("conn reset")

    with pytest.raises(ProviderAPIError):
        _call(handler, max_attempts=3)
    assert len(calls) == 3  # retried, not failed on first raw error


# ── Settings: blank optional int env vars must mean "unset", not crash ──────


def test_blank_int_settings_do_not_crash_boot():
    s = Settings(
        mail_default_relayhost_id="", registry_keep_images="", _env_file=None
    )
    assert s.mail_default_relayhost_id == 0
    assert s.registry_keep_images == 0
