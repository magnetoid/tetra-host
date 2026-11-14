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


def test_two_factor_status_is_read_only_and_enable_disable_absent():
    server = MCPServer(_noop_client(), allow_writes=True)
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert "two_factor_status" in names
    # Enabling/disabling 2FA is human-only — never an MCP tool, even with writes on.
    assert not names & {"two_factor_enable", "two_factor_disable", "enable_2fa"}


def test_notification_channels_read_only_no_write_tools():
    server = MCPServer(_noop_client(), allow_writes=True)
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert "list_notification_channels" in names
    assert not names & {"create_notification_channel", "delete_notification_channel", "test_notification"}


def test_call_list_notification_channels():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/account/notifications"
        return httpx.Response(200, json=[{"id": "n1", "name": "slack", "url": "https://x", "enabled": True}])

    server = MCPServer(make_client(handler))
    response = server.handle_message(
        _rpc("tools/call", {"name": "list_notification_channels", "arguments": {}})
    )
    assert response["result"]["isError"] is False
    assert "slack" in response["result"]["content"][0]["text"]


def test_uptime_monitors_read_only():
    server = MCPServer(_noop_client(), allow_writes=True)
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert "list_uptime_monitors" in names
    assert not names & {"create_uptime_monitor", "delete_uptime_monitor", "check_uptime_monitor"}


def test_call_list_uptime_monitors():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/account/monitors"
        return httpx.Response(200, json=[{"id": "m1", "name": "site", "status": "up"}])

    server = MCPServer(make_client(handler))
    response = server.handle_message(_rpc("tools/call", {"name": "list_uptime_monitors", "arguments": {}}))
    assert response["result"]["isError"] is False
    assert "site" in response["result"]["content"][0]["text"]


def test_call_two_factor_status_returns_state():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/account/2fa"
        return httpx.Response(200, json={"enabled": True, "backup_codes_remaining": 7})

    server = MCPServer(make_client(handler))
    response = server.handle_message(_rpc("tools/call", {"name": "two_factor_status", "arguments": {}}))
    assert response["result"]["isError"] is False
    assert "enabled" in response["result"]["content"][0]["text"]


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


def test_explain_deployment_is_a_read_tool():
    server = MCPServer(_noop_client())
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert "explain_deployment" in names  # available without --allow-writes


def test_call_explain_deployment_hits_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/deploys/dep-9/explain"
        return httpx.Response(200, json={"summary": "No Dockerfile", "category": "build-config",
                                         "source": "heuristic"})

    server = MCPServer(make_client(handler))
    response = server.handle_message(
        _rpc("tools/call", {"name": "explain_deployment", "arguments": {"deployment_id": "dep-9"}})
    )
    assert response["result"]["isError"] is False
    assert "No Dockerfile" in response["result"]["content"][0]["text"]


def test_explain_error_is_a_read_tool():
    server = MCPServer(_noop_client())
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert "explain_error" in names  # available without --allow-writes


def test_api_tokens_list_only_never_create_or_revoke():
    # list is a read tool; create (secret reveal) + revoke stay human-only, even with writes on.
    server = MCPServer(_noop_client(), allow_writes=True)
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert "list_api_tokens" in names
    assert not any("token" in n and n != "list_api_tokens" for n in names)


def test_call_explain_error_hits_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/apps/app-7/errors/42/explain"
        return httpx.Response(200, json={"issue_id": "42", "title": "TypeError",
                                         "summary": "type error", "category": "type-error",
                                         "source": "heuristic"})

    server = MCPServer(make_client(handler))
    response = server.handle_message(
        _rpc("tools/call",
             {"name": "explain_error", "arguments": {"project": "app-7", "issue_id": "42"}})
    )
    assert response["result"]["isError"] is False
    assert "type error" in response["result"]["content"][0]["text"]


# ── Mail tools (Phase 2) ────────────────────────────────────────────────────


def test_mail_tools_read_write_split():
    server = MCPServer(_noop_client(), allow_writes=True)
    tools = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert {"mail_overview", "list_mail_aliases", "get_mail_dkim"} <= tools
    assert {"create_mail_domain", "delete_mail_domain", "create_mail_alias", "delete_mail_alias"} <= tools
    # Mailbox creation is deliberately absent: passwords must not transit MCP.
    assert not any("mailbox" in name for name in tools)


def test_create_mail_domain_write_gated():
    server = MCPServer(_noop_client())  # read-only
    response = server.handle_message(
        _rpc("tools/call", {"name": "create_mail_domain",
                            "arguments": {"domain": "acme.test", "confirm": True}})
    )
    assert response["result"]["isError"] is True


def test_confirmed_create_mail_domain_calls_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/api/v1/mail/domains"
        assert json.loads(request.content)["domain"] == "acme.test"
        return httpx.Response(200, json={"domain": "acme.test", "dns_records": []})

    server = MCPServer(make_client(handler), allow_writes=True)
    response = server.handle_message(
        _rpc("tools/call", {"name": "create_mail_domain",
                            "arguments": {"domain": "acme.test", "confirm": True}})
    )
    assert response["result"].get("isError") is not True


def test_get_mail_dkim_is_read_tool():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/mail/domains/acme.test/dkim"
        return httpx.Response(200, json={"domain": "acme.test", "dkim_name": "n", "dkim_txt": "t"})

    server = MCPServer(make_client(handler))  # read-only server can still call it
    response = server.handle_message(
        _rpc("tools/call", {"name": "get_mail_dkim", "arguments": {"domain": "acme.test"}})
    )
    assert response["result"].get("isError") is not True


def test_bad_typed_argument_is_tool_error_not_crash():
    server = MCPServer(_noop_client(), allow_writes=True)
    response = server.handle_message(
        _rpc("tools/call", {"name": "delete_mail_alias",
                            "arguments": {"alias_id": "six", "confirm": True}})
    )
    result = response["result"]
    assert result["isError"] is True
    assert "Invalid argument" in result["content"][0]["text"]
    # The server must still answer subsequent calls (loop survives).
    assert server.handle_message(_rpc("ping"))["result"] == {}


def test_workspace_tools_are_read_only():
    names = {t["name"] for t in MCPServer(_noop_client(), allow_writes=True).handle_message(
        _rpc("tools/list"))["result"]["tools"]}
    assert {"list_teams", "get_team", "list_team_projects", "list_environments",
            "list_team_apps"} <= names
    # Hierarchy writes and the platform-wide list stay off the agent surface (ADR 0012).
    assert not names & {"create_project", "move_app", "delete_project", "list_platform_apps"}
    read_only = {t["name"] for t in MCPServer(_noop_client()).handle_message(
        _rpc("tools/list"))["result"]["tools"]}
    assert "list_team_apps" in read_only


def test_call_list_team_apps_passes_filters():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/teams/alpha/apps"
        assert dict(request.url.params) == {"project": "shop"}
        return httpx.Response(200, json=[{"name": "shop"}])

    response = MCPServer(make_client(handler)).handle_message(
        _rpc("tools/call", {"name": "list_team_apps", "arguments": {"team": "alpha", "project": "shop"}})
    )
    assert response["result"]["isError"] is False


def test_restart_and_cancel_are_gated_writes_and_volumes_is_a_read():
    read_only = {
        t["name"] for t in MCPServer(_noop_client()).handle_message(_rpc("tools/list"))
        ["result"]["tools"]
    }
    assert "app_volumes" in read_only
    assert not read_only & {"restart_app", "cancel_deployment"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/api/v1/deploys/dep-7/cancel"
        return httpx.Response(200, json={"deployment_id": "dep-7", "status": "cancelled"})

    server = MCPServer(make_client(handler), allow_writes=True)
    unconfirmed = server.handle_message(
        _rpc("tools/call", {"name": "cancel_deployment", "arguments": {"deployment_id": "dep-7"}})
    )["result"]
    assert unconfirmed["isError"] is True
    confirmed = server.handle_message(
        _rpc("tools/call", {"name": "cancel_deployment",
                            "arguments": {"deployment_id": "dep-7", "confirm": True}})
    )["result"]
    assert confirmed["isError"] is False and "cancelled" in confirmed["content"][0]["text"]


def test_database_tools_hide_passwords_restore_and_delete():
    server = MCPServer(_noop_client(), allow_writes=True)
    names = {t["name"] for t in server.handle_message(_rpc("tools/list"))["result"]["tools"]}
    assert {"list_databases", "database_backups", "create_database", "backup_database",
            "link_database"} <= names
    # Credentials and data-destroying operations stay human-only.
    assert not {n for n in names if "connection" in n or "restore" in n or "delete_database" in n}
    read_only = {t["name"] for t in MCPServer(_noop_client()).handle_message(
        _rpc("tools/list"))["result"]["tools"]}
    assert "list_databases" in read_only and "create_database" not in read_only


def test_create_database_requires_confirm():
    calls: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "db-1", "name": "blog-db"})

    server = MCPServer(make_client(handler), allow_writes=True)
    args = {"name": "blog-db", "engine": "postgres"}
    refused = server.handle_message(
        _rpc("tools/call", {"name": "create_database", "arguments": args})
    )
    assert refused["result"]["isError"] is True and calls == []
    done = server.handle_message(
        _rpc("tools/call", {"name": "create_database", "arguments": {**args, "confirm": True}})
    )
    assert done["result"]["isError"] is False
    assert calls == [{"name": "blog-db", "engine": "postgres"}]


def test_create_database_passes_environment_id():
    calls: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "db-1", "name": "blog-db"})

    server = MCPServer(make_client(handler), allow_writes=True)
    args = {"name": "blog-db", "engine": "postgres", "environment_id": "env-1", "confirm": True}
    done = server.handle_message(_rpc("tools/call", {"name": "create_database", "arguments": args}))
    assert done["result"]["isError"] is False
    assert calls == [{"name": "blog-db", "engine": "postgres", "environment_id": "env-1"}]
