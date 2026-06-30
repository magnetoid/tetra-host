"""Coolify deployment parsing — regression tests pinned to the live v4 API shape.

Verified against a running Coolify 4.1.2: the deployments-by-application endpoint
returns ``{"count": N, "deployments": [...]}`` (array under ``deployments``, NOT
``data``), and each deployment carries its build log under ``logs`` (a JSON-array
string), NOT ``deployment_log``. Both were mismapped, so the project Logs page
showed bogus/empty deployments and streamed no log text.
"""

import asyncio

import httpx

from app.cache import TTLCache
from app.services.coolify import (
    CoolifyClient,
    normalize_coolify_deployment,
    parse_deployment_log_lines,
)


def test_normalize_reads_logs_field():
    raw = {
        "deployment_uuid": "dep-1",
        "status": "finished",
        "commit": "abc1234",
        "logs": '[{"output": "Building image", "type": "stdout", "timestamp": "2026-06-27T02:11:26Z"}]',
    }
    d = normalize_coolify_deployment(raw)
    assert d.id == "dep-1"
    assert d.status == "finished"
    assert d.deployment_log  # populated from "logs", not empty
    lines = parse_deployment_log_lines(d.deployment_log)
    assert lines and lines[0]["output"] == "Building image"


def test_normalize_falls_back_to_deployment_log():
    d = normalize_coolify_deployment({"uuid": "x", "deployment_log": "plain line"})
    assert d.deployment_log == "plain line"


def _client(handler) -> CoolifyClient:
    return CoolifyClient(
        base_url="https://coolify.test",
        token="tok",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        cache=TTLCache(),
    )


def test_list_deployments_reads_deployments_key_not_dict_keys():
    body = {
        "count": 2,
        "deployments": [
            {"deployment_uuid": "dep-1", "status": "finished", "commit": "aaa", "logs": "[]"},
            {"deployment_uuid": "dep-2", "status": "in_progress", "commit": "bbb", "logs": "[]"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/deployments/applications/app-1"
        return httpx.Response(200, json=body)

    deployments = asyncio.run(_client(handler).list_deployments_for_application("app-1"))
    ids = [d.id for d in deployments]
    assert ids == ["dep-1", "dep-2"]  # the real deployments…
    assert "count" not in ids and "deployments" not in ids  # …not the wrapper dict's keys
    assert deployments[0].status == "finished"


def test_list_deployments_tolerates_empty_and_bare_list():
    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"count": 0, "deployments": []})

    assert asyncio.run(_client(empty).list_deployments_for_application("app-1")) == []

    def bare(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"deployment_uuid": "d9", "status": "finished"}])

    out = asyncio.run(_client(bare).list_deployments_for_application("app-1"))
    assert [d.id for d in out] == ["d9"]
