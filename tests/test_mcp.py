"""Tetra MCP server: JSON-RPC handshake, curated tools, human-gated writes."""

import io
import json

import httpx

from tetra_cli.client import TetraClient
from tetra_cli.mcp import PROTOCOL_VERSION, MCPServer, serve_stdio


def make_client(handler) -> TetraClient:
    return TetraClient("http://panel.test", "tok", transport=httpx.MockTransport(handler))


def _noop_client() -> TetraClient:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no HTTP call expected")

    return make_client(handler)


def _rpc(method: str, params: dict | None = None, id_: int | None = 1) -> dict:
    message: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        message["params"] = params
    if id_ is not None:
        message["id"] = id_
    return message


# ── Handshake ──────────────────────────────────────────────────────────────


def test_initialize_handshake():
    server = MCPServer(_noop_client())
    response = server.handle_message(
        _rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                            "clientInfo": {"name": "test", "version": "0"}})
    )
    assert response["id"] == 1
    result = response["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == "tetra-mcp"
    assert "tools" in result["capabilities"]


def test_initialized_notification_gets_no_response():
    server = MCPServer(_noop_client())
    assert server.handle_message(_rpc("notifications/initialized", id_=None)) is None


def test_unknown_method_returns_method_not_found():
    server = MCPServer(_noop_client())
    response = server.handle_message(_rpc("bogus/method"))
    assert response["error"]["code"] == -32601


def test_ping_pongs():
    server = MCPServer(_noop_client())
    assert server.handle_message(_rpc("ping"))["result"] == {}


# ── Tool listing (write tools hidden unless enabled) ───────────────────────


def test_tools_list_read_only_by_default():
    server = MCPServer(_noop_client())
    tools = server.handle_message(_rpc("tools/list"))["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert "list_apps" in names and "list_previews" in names and "get_deployment" in names
    assert not names & {"deploy_git", "rollback_deployment", "teardown_preview", "set_env_var"}
    for tool in tools:  # every tool is fully typed
        assert tool["description"] and tool["inputSchema"]["type"] == "object"


def test_tools_list_includes_writes_when_enabled():
    server = MCPServer(_noop_client(), allow_writes=True)
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert {"deploy_git", "rollback_deployment", "teardown_preview", "set_env_var"} <= names


# ── Read tools ─────────────────────────────────────────────────────────────


def test_call_list_apps_returns_inventory():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/apps"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json=[{"project": "blog", "status": "running"}])

    server = MCPServer(make_client(handler))
    response = server.handle_message(_rpc("tools/call", {"name": "list_apps", "arguments": {}}))
    result = response["result"]
    assert result["isError"] is False
    assert "blog" in result["content"][0]["text"]


def test_call_get_deployment_passes_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/deploys/dep-9"
        return httpx.Response(200, json={"id": "dep-9", "status": "ready", "log": "✓ built"})

    server = MCPServer(make_client(handler))
    response = server.handle_message(
        _rpc("tools/call", {"name": "get_deployment", "arguments": {"deployment_id": "dep-9"}})
    )
    assert "ready" in response["result"]["content"][0]["text"]


def test_provider_error_surfaces_as_tool_error_not_crash():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"detail": "Quota exceeded"})

    server = MCPServer(make_client(handler))
    response = server.handle_message(_rpc("tools/call", {"name": "list_apps", "arguments": {}}))
    result = response["result"]
    assert result["isError"] is True
    assert "Quota exceeded" in result["content"][0]["text"]


def test_call_unknown_tool_is_an_error_result():
    server = MCPServer(_noop_client())
    response = server.handle_message(_rpc("tools/call", {"name": "nope", "arguments": {}}))
    assert response["result"]["isError"] is True


# ── Write gating (ADR: writes are human-gated) ─────────────────────────────


def test_write_tool_rejected_when_writes_disabled():
    server = MCPServer(_noop_client())  # read-only server
    response = server.handle_message(
        _rpc("tools/call", {"name": "deploy_git",
                            "arguments": {"git_url": "https://github.com/x/y", "name": "blog",
                                          "confirm": True}})
    )
    result = response["result"]
    assert result["isError"] is True
    assert "allow-writes" in result["content"][0]["text"]


def test_write_tool_requires_explicit_confirm():
    server = MCPServer(_noop_client(), allow_writes=True)
    response = server.handle_message(
        _rpc("tools/call", {"name": "deploy_git",
                            "arguments": {"git_url": "https://github.com/x/y", "name": "blog"}})
    )
    result = response["result"]
    assert result["isError"] is True
    assert "confirm" in result["content"][0]["text"]


def test_confirmed_write_deploys():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/api/v1/deploys/git"
        body = json.loads(request.content)
        assert body["git_url"] == "https://github.com/x/y" and body["name"] == "blog"
        return httpx.Response(200, json={"deployment_id": "dep-1", "status": "queued"})

    server = MCPServer(make_client(handler), allow_writes=True)
    response = server.handle_message(
        _rpc("tools/call", {"name": "deploy_git",
                            "arguments": {"git_url": "https://github.com/x/y", "name": "blog",
                                          "confirm": True}})
    )
    result = response["result"]
    assert result["isError"] is False and "dep-1" in result["content"][0]["text"]


# ── stdio loop ─────────────────────────────────────────────────────────────


def test_serve_stdio_round_trip():
    lines = "\n".join([
        json.dumps(_rpc("initialize", {"protocolVersion": PROTOCOL_VERSION})),
        json.dumps(_rpc("notifications/initialized", id_=None)),
        json.dumps(_rpc("tools/list", id_=2)),
    ])
    stdout = io.StringIO()
    serve_stdio(_noop_client(), stdin=io.StringIO(lines + "\n"), stdout=stdout)
    responses = [json.loads(line) for line in stdout.getvalue().strip().split("\n")]
    assert len(responses) == 2  # the notification produces no output
    assert responses[0]["result"]["serverInfo"]["name"] == "tetra-mcp"
    assert any(t["name"] == "list_apps" for t in responses[1]["result"]["tools"])


def test_serve_stdio_skips_malformed_lines():
    lines = "not-json\n" + json.dumps(_rpc("ping", id_=3)) + "\n"
    stdout = io.StringIO()
    serve_stdio(_noop_client(), stdin=io.StringIO(lines), stdout=stdout)
    [response] = [json.loads(line) for line in stdout.getvalue().strip().split("\n")]
    assert response["id"] == 3 and response["result"] == {}
