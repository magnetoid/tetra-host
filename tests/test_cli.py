import json

import httpx
import pytest

from tetra_cli.cli import build_parser, main
from tetra_cli.client import TetraClient, TetraError


def make_client(handler, token: str = "tok") -> TetraClient:
    return TetraClient("http://panel.test", token, transport=httpx.MockTransport(handler))


# ── client ────────────────────────────────────────────────────────────────


def test_client_login_sends_credentials_and_keeps_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"token": "abc123", "admin": {"email": "a@b.c"}})

    client = make_client(handler, token="")
    token = client.login("a@b.c", "secretpass")
    assert token == "abc123"
    assert client.token == "abc123"
    assert seen["path"] == "/api/v1/auth/login"
    assert seen["body"] == {"email": "a@b.c", "password": "secretpass"}


def test_client_deploy_passes_force_and_returns_deployment_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/sites/app-1/deploy"
        assert request.url.params.get("force") == "1"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"ok": True, "message": "queued", "deployment_id": "dep-9"})

    result = make_client(handler).deploy("app-1", force=True)
    assert result["deployment_id"] == "dep-9"


def test_client_dns_add_builds_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/dns/zones/z1/records"
        assert json.loads(request.content) == {
            "type": "A", "name": "app", "content": "1.2.3.4", "ttl": 1, "proxied": False,
        }
        return httpx.Response(200, json={"message": "DNS record created."})

    make_client(handler).dns_add("z1", "A", "app", "1.2.3.4")


def test_client_dns_update_uses_put_with_priority():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/api/v1/dns/zones/z1/records/r1"
        body = json.loads(request.content)
        assert body["type"] == "MX" and body["priority"] == 5
        return httpx.Response(200, json={"message": "DNS record updated."})

    make_client(handler).dns_update("z1", "r1", "MX", "mail", "mx.example.com", priority=5)


def test_client_zone_set_uses_patch():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/v1/dns/zones/z1/settings"
        assert json.loads(request.content) == {"setting": "ssl", "value": "full"}
        return httpx.Response(200, json={"message": "ssl updated."})

    make_client(handler).zone_set("z1", "ssl", "full")


def test_client_raises_on_error_with_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "Zone is not assigned to this tenant."})

    with pytest.raises(TetraError) as exc:
        make_client(handler).dns_rm("z1", "r1")
    assert exc.value.status == 403
    assert "not assigned" in str(exc.value)


def test_client_stream_logs_parses_sse():
    sse = (
        "event: status\ndata: {\"status\": \"in_progress\"}\n\n"
        "event: log\ndata: {\"output\": \"Building\", \"type\": \"stdout\"}\n\n"
        "event: log\ndata: {\"output\": \"boom\", \"type\": \"stderr\"}\n\n"
        "event: done\ndata: {\"status\": \"finished\"}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/sites/app-1/deployments/dep-1/logs/stream"
        return httpx.Response(200, text=sse)

    events = list(make_client(handler).stream_logs("app-1", "dep-1"))
    assert [e for e, _ in events] == ["status", "log", "log", "done"]
    assert events[1][1]["output"] == "Building"
    assert events[3][1]["status"] == "finished"


# ── CLI ───────────────────────────────────────────────────────────────────


def test_parser_dispatches_subcommands():
    parser = build_parser()
    args = parser.parse_args(["deploy", "app-1", "--force", "--follow"])
    assert args.command == "deploy" and args.site == "app-1" and args.force and args.follow
    args = parser.parse_args(["dns", "add", "z1", "A", "app", "1.2.3.4", "--proxied"])
    assert args.func is not None and args.proxied is True


def test_main_sites_renders_table(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[
            {"id": "app-1", "name": "App One", "status": "running", "primary_domain": "a.test"},
        ])

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["sites"])
    out = capsys.readouterr().out
    assert code == 0
    assert "app-1" in out and "App One" in out


def test_main_logs_streams_and_reports_failure(monkeypatch, capsys):
    sse = (
        "event: log\ndata: {\"output\": \"step\", \"type\": \"stdout\"}\n\n"
        "event: done\ndata: {\"status\": \"failed\"}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sse)

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["logs", "app-1", "dep-1"])
    out = capsys.readouterr().out
    assert "step" in out
    assert code == 1  # terminal status was "failed"


def test_main_requires_login(monkeypatch, tmp_path):
    monkeypatch.setenv("TETRA_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("TETRA_TOKEN", raising=False)
    code = main(["sites"])
    assert code == 1  # not logged in
