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
        assert request.url.path == "/api/v1/projects/app-1/deploy"
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


def test_client_zone_analytics_passes_days():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/dns/zones/z1/analytics"
        assert request.url.params.get("days") == "30"
        return httpx.Response(200, json={"zone_id": "z1", "points": [], "totals": {"requests": 0}})

    result = make_client(handler).zone_analytics("z1", days=30)
    assert result["zone_id"] == "z1"


def test_client_dns_export_gets_bind():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/dns/zones/z1/export"
        return httpx.Response(200, json={"zone_id": "z1", "bind": "www 1 IN A 1.2.3.4\n", "record_count": 1})

    result = make_client(handler).dns_export("z1")
    assert result["record_count"] == 1


def test_client_dns_import_posts_bind_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/dns/zones/z1/import"
        assert json.loads(request.content) == {"bind": "www 1 IN A 1.2.3.4\n"}
        return httpx.Response(200, json={"message": "Imported 1 records."})

    result = make_client(handler).dns_import("z1", "www 1 IN A 1.2.3.4\n")
    assert result["message"] == "Imported 1 records."


def test_client_apps_install_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/apps/install"
        assert json.loads(request.content) == {"slug": "wordpress-with-mariadb", "name": "blog"}
        return httpx.Response(200, json={"message": "App installed.", "project": "blog", "domain": ""})

    result = make_client(handler).apps_install("wordpress-with-mariadb", name="blog")
    assert result["project"] == "blog"


def test_client_apps_catalog_passes_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/apps/catalog"
        assert request.url.params.get("search") == "wordpress"
        return httpx.Response(200, json=[{"slug": "wordpress-with-mysql", "name": "WordPress"}])

    result = make_client(handler).apps_catalog(search="wordpress")
    assert result[0]["slug"] == "wordpress-with-mysql"


def test_client_deploy_git_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/deploys/git"
        assert json.loads(request.content) == {
            "git_url": "https://github.com/x/y", "ref": "main", "name": "demo", "port": 8080,
        }
        return httpx.Response(200, json={"ok": True, "deployment_id": "dep-1", "status": "queued"})

    result = make_client(handler).deploy_git("https://github.com/x/y", name="demo", port=8080)
    assert result["deployment_id"] == "dep-1"


def test_client_rollback_deploy_posts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/deploys/dep-1/rollback"
        return httpx.Response(200, json={"ok": True, "deployment_id": "dep-2", "status": "queued"})

    result = make_client(handler).rollback_deploy("dep-1")
    assert result["deployment_id"] == "dep-2"


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
        assert request.url.path == "/api/v1/projects/app-1/deployments/dep-1/logs/stream"
        return httpx.Response(200, text=sse)

    events = list(make_client(handler).stream_logs("app-1", "dep-1"))
    assert [e for e, _ in events] == ["status", "log", "log", "done"]
    assert events[1][1]["output"] == "Building"
    assert events[3][1]["status"] == "finished"


def test_client_stream_deploy_logs_parses_sse():
    # Native deploy stream: `log` events carry a raw line string, status/done carry dicts.
    sse = (
        'event: status\ndata: {"status": "building"}\n\n'
        'event: log\ndata: "cloning repo"\n\n'
        'event: log\ndata: "built image"\n\n'
        'event: done\ndata: {"status": "ready"}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/deploys/dep-9/logs/stream"
        return httpx.Response(200, text=sse)

    events = list(make_client(handler).stream_deploy_logs("dep-9"))
    assert [e for e, _ in events] == ["status", "log", "log", "done"]
    assert events[1][1] == "cloning repo"
    assert events[3][1]["status"] == "ready"


def test_client_deploy_env_set_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/deploys/blog/env"
        body = json.loads(request.content)
        assert body == {"key": "API_KEY", "value": "sk-x", "is_secret": True, "is_build_time": False}
        return httpx.Response(200, json=[])

    make_client(handler).deploy_env_set("blog", "API_KEY", "sk-x", is_secret=True)


def test_client_deploy_env_rm_deletes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/v1/deploys/blog/env/API_KEY"
        return httpx.Response(200, json={"ok": True})

    make_client(handler).deploy_env_rm("blog", "API_KEY")


def test_client_create_deploy_hook_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/deploy-hooks"
        body = json.loads(request.content)
        assert body == {"project": "blog", "git_url": "https://github.com/x/y", "ref": "main", "port": 3000}
        return httpx.Response(200, json={"id": "h1", "url": "u", "secret": "s", "project": "blog", "ref": "main"})

    result = make_client(handler).create_deploy_hook("blog", "https://github.com/x/y")
    assert result["secret"] == "s"


def test_client_domain_add_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/domains"
        assert json.loads(request.content) == {"project": "blog", "hostname": "www.example.com"}
        return httpx.Response(200, json={"id": "d1", "hostname": "www.example.com", "status": "pending"})

    result = make_client(handler).domain_add("blog", "www.example.com")
    assert result["status"] == "pending"


def test_client_domain_verify_posts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/domains/d1/verify"
        return httpx.Response(200, json={"id": "d1", "status": "verified"})

    assert make_client(handler).domain_verify("d1")["status"] == "verified"


def test_client_apps_compute_gets():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/apps/blog/compute"
        return httpx.Response(200, json={"project": "blog", "samples": [], "cpu_percent": 0, "mem_used_mb": 0})

    result = make_client(handler).apps_compute("blog")
    assert result["project"] == "blog"


# ── CLI ───────────────────────────────────────────────────────────────────


def test_parser_dispatches_subcommands():
    parser = build_parser()
    args = parser.parse_args(["deploy", "app-1", "--force", "--follow"])
    assert args.command == "deploy" and args.project == "app-1" and args.force and args.follow
    args = parser.parse_args(["dns", "add", "z1", "A", "app", "1.2.3.4", "--proxied"])
    assert args.func is not None and args.proxied is True
    args = parser.parse_args(["dns", "export", "z1", "-o", "zone.txt"])
    assert args.zone == "z1" and args.output == "zone.txt"
    args = parser.parse_args(["dns", "import", "z1", "zone.txt"])
    assert args.zone == "z1" and args.file == "zone.txt"
    args = parser.parse_args(["cf", "analytics", "z1", "--days", "14"])
    assert args.zone == "z1" and args.days == 14
    args = parser.parse_args(["apps", "install", "wordpress-with-mariadb", "--name", "blog"])
    assert args.slug == "wordpress-with-mariadb" and args.name == "blog"
    args = parser.parse_args(["apps", "catalog", "--search", "wp"])
    assert args.search == "wp"


def test_main_projects_renders_table(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/projects"
        return httpx.Response(200, json=[
            {"id": "app-1", "name": "App One", "status": "running", "primary_domain": "a.test"},
        ])

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["projects"])
    out = capsys.readouterr().out
    assert code == 0
    assert "app-1" in out and "App One" in out


def test_main_logs_streams_and_reports_failure(monkeypatch, capsys):
    sse = (
        "event: log\ndata: {\"output\": \"step\", \"type\": \"stdout\"}\n\n"
        "event: done\ndata: {\"status\": \"failed\"}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/projects/app-1/deployments/dep-1/logs/stream"
        return httpx.Response(200, text=sse)

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["logs", "app-1", "dep-1"])
    out = capsys.readouterr().out
    assert "step" in out
    assert code == 1  # terminal status was "failed"


def test_main_deploys_git_streams_sse_then_reports_domain(monkeypatch, capsys):
    sse = (
        'event: status\ndata: {"status": "building"}\n\n'
        'event: log\ndata: "cloning repo"\n\n'
        'event: done\ndata: {"status": "ready"}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/deploys/git":
            return httpx.Response(200, json={"deployment_id": "dep-42"})
        if path == "/api/v1/deploys/dep-42/logs/stream":
            return httpx.Response(200, text=sse)
        if path == "/api/v1/deploys/dep-42":
            return httpx.Response(200, json={"status": "ready", "domain": "demo.apps.test"})
        return httpx.Response(404)

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["deploys", "git", "https://github.com/x/y", "--name", "demo"])
    out = capsys.readouterr().out
    assert code == 0
    assert "cloning repo" in out
    assert "deployed" in out and "demo.apps.test" in out


def test_main_requires_login(monkeypatch, tmp_path):
    monkeypatch.setenv("TETRA_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("TETRA_TOKEN", raising=False)
    code = main(["projects"])
    assert code == 1  # not logged in


# ── Plans client ──────────────────────────────────────────────────────────


def test_client_plans_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/plans"
        assert request.url.params.get("include_archived") in (None, "false", "False")
        return httpx.Response(200, json=[
            {"id": 1, "key": "starter", "name": "Starter", "price_cents": 900, "currency": "USD",
             "max_apps": 1, "max_domains": 3, "is_archived": False},
        ])

    result = make_client(handler).plans()
    assert isinstance(result, list)
    assert result[0]["key"] == "starter"


def test_client_plans_include_archived_passes_param():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/plans"
        assert request.url.params.get("include_archived") in ("true", "True", "1")
        return httpx.Response(200, json=[])

    make_client(handler).plans(include_archived=True)


def test_client_plan_create_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/plans"
        body = json.loads(request.content)
        assert body["key"] == "pro" and body["name"] == "Pro" and body["price_cents"] == 2900
        return httpx.Response(201, json={"id": 2, "key": "pro", "name": "Pro"})

    result = make_client(handler).plan_create(
        key="pro", name="Pro", price_cents=2900, currency="USD",
        max_apps=5, max_domains=10,
    )
    assert result["key"] == "pro"


def test_client_plan_update_uses_patch():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/v1/plans/3"
        body = json.loads(request.content)
        assert body == {"name": "Pro Plus", "price_cents": 3900}
        return httpx.Response(200, json={"id": 3, "name": "Pro Plus"})

    result = make_client(handler).plan_update(3, name="Pro Plus", price_cents=3900)
    assert result["name"] == "Pro Plus"


def test_client_plan_archive_posts_to_archive():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/plans/7/archive"
        return httpx.Response(200, json={"id": 7, "is_archived": True})

    result = make_client(handler).plan_archive(7)
    assert result["is_archived"] is True


# ── Tenants client ────────────────────────────────────────────────────────


def test_client_tenants_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/tenants"
        return httpx.Response(200, json=[
            {"id": 1, "name": "Acme", "slug": "acme", "is_active": True,
             "status": "active", "plan_key": "starter"},
        ])

    result = make_client(handler).tenants()
    assert isinstance(result, list)
    assert result[0]["slug"] == "acme"


def test_client_tenant_action_approve_posts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/tenants/acme/approve"
        return httpx.Response(200, json={"id": 1, "slug": "acme", "status": "active"})

    result = make_client(handler).tenant_action("acme", "approve")
    assert result["status"] == "active"


def test_client_tenant_action_suspend_posts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/tenants/acme/suspend"
        return httpx.Response(200, json={"id": 1, "slug": "acme", "status": "suspended"})

    result = make_client(handler).tenant_action("acme", "suspend")
    assert result["status"] == "suspended"


# ── Usage client + CLI ────────────────────────────────────────────────────


def test_client_usage_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/usage"
        return httpx.Response(200, json={
            "plan_key": "starter",
            "apps_used": 1, "apps_limit": 3,
            "cpu_millicores_used": 500, "cpu_millicores_limit": 8000,
            "mem_mb_used": 512, "mem_mb_limit": 4096,
            "disk_mb_used": 1024, "disk_mb_limit": 20480,
            "domains_used": 2, "domains_limit": 5,
            "enforced": ["apps"],
        })

    result = make_client(handler).usage()
    assert result["apps_used"] == 1
    assert result["apps_limit"] == 3
    assert result["enforced"] == ["apps"]


def test_main_usage_renders_table(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "plan_key": "pro",
            "apps_used": 2, "apps_limit": 10,
            "cpu_millicores_used": 1000, "cpu_millicores_limit": 8000,
            "mem_mb_used": 256, "mem_mb_limit": 4096,
            "disk_mb_used": 512, "disk_mb_limit": 20480,
            "domains_used": 1, "domains_limit": 5,
            "enforced": ["apps"],
        })

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["usage"])
    out = capsys.readouterr().out
    assert code == 0
    assert "pro" in out
    assert "2/10" in out
    assert "advisory" in out


# ── Databases client ──────────────────────────────────────────────────────


def test_client_databases_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/databases"
        return httpx.Response(200, json=[
            {"uuid": "db-uuid-1", "name": "mydb", "type": "postgresql", "status": "running"},
        ])

    result = make_client(handler).databases()
    assert isinstance(result, list)
    assert result[0]["uuid"] == "db-uuid-1"


def test_client_provision_database_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/databases"
        body = json.loads(request.content)
        assert body == {
            "type": "postgresql",
            "name": "mydb",
            "server_uuid": "srv-1",
            "project_uuid": "proj-1",
            "environment_name": "production",
        }
        return httpx.Response(201, json={"uuid": "db-uuid-1", "name": "mydb", "type": "postgresql"})

    result = make_client(handler).provision_database(
        "postgresql", "mydb", "srv-1", "proj-1", "production"
    )
    assert result["uuid"] == "db-uuid-1"


def test_client_database_backups_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/databases/db-uuid-1/backups"
        return httpx.Response(200, json=[
            {"uuid": "bk-1", "status": "success", "created_at": "2026-06-28T12:00:00Z"},
        ])

    result = make_client(handler).database_backups("db-uuid-1")
    assert isinstance(result, list)
    assert result[0]["uuid"] == "bk-1"


def test_client_create_database_backup_posts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/databases/db-uuid-1/backups"
        return httpx.Response(200, json={"message": "Backup queued."})

    result = make_client(handler).create_database_backup("db-uuid-1")
    assert result["message"] == "Backup queued."


# ── Admin overview (super-admin command center) ───────────────────────────


def test_client_admin_overview_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/admin/overview"
        return httpx.Response(200, json={
            "tenant_status": {"active": 3, "pending": 1, "suspended": 0, "rejected": 0, "total": 4},
            "totals": {"tenants": 4, "admins": 5, "apps": 2, "databases": 1, "plans": 3},
            "committed_resources": {"cpu_millicores": 1500, "mem_mb": 1536, "disk_mb": 6144},
            "pending_tenants": [{"slug": "newco", "name": "New Co", "plan_key": ""}],
            "recent_events": [
                {"actor_email": "admin@x", "action": "tenant.approve", "target": "acme",
                 "details": "", "created_at": "2026-06-30T10:00:00+00:00"},
            ],
        })

    result = make_client(handler).admin_overview()
    assert result["tenant_status"]["total"] == 4
    assert result["pending_tenants"][0]["slug"] == "newco"


def test_parser_admin_overview_dispatches():
    args = build_parser().parse_args(["admin", "overview"])
    assert args.command == "admin" and args.admin_cmd == "overview"
    assert args.func is not None


def test_client_project_runtime_logs_passes_lines():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/projects/app-1/logs"
        assert request.url.params.get("lines") == "300"
        return httpx.Response(200, json={"logs": "line a\nline b"})

    result = make_client(handler).project_runtime_logs("app-1", lines=300)
    assert result["logs"] == "line a\nline b"


def test_parser_runtime_logs_dispatches():
    args = build_parser().parse_args(["runtime-logs", "app-1", "--lines", "500"])
    assert args.command == "runtime-logs" and args.project == "app-1" and args.lines == 500


def test_client_project_analytics_passes_period():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/projects/app-1/analytics"
        assert request.url.params.get("period") == "30d"
        return httpx.Response(200, json={"configured": True, "ready": True, "summary": {"visitors": 9}})

    result = make_client(handler).project_analytics("app-1", period="30d")
    assert result["summary"]["visitors"] == 9


def test_main_analytics_renders(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "configured": True, "ready": True, "period": "7d",
            "summary": {"visitors": 12, "pageviews": 34, "bounce_rate": 40, "avg_seconds": 51},
            "top_pages": [{"label": "/", "count": 20}],
            "top_referrers": [{"label": "google.com", "count": 5}],
            "tracking_snippet": "<script ...></script>",
        })

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["analytics", "app-1", "--period", "7d"])
    out = capsys.readouterr().out
    assert code == 0
    assert "visitors=12" in out and "google.com" in out


def test_client_project_errors_issues_get():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/projects/app-1/errors"
        return httpx.Response(200, json={"configured": True, "ready": True, "issues": []})

    result = make_client(handler).project_errors("app-1")
    assert result["ready"] is True


def test_main_errors_renders(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "configured": True, "ready": True, "project_slug": "web",
            "dsn": "https://abc@gt.test/1",
            "issues": [{"level": "error", "count": 7, "title": "TypeError: boom"}],
        })

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["errors", "app-1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "TypeError: boom" in out and "gt.test" in out


def test_main_admin_overview_renders(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/admin/overview"
        return httpx.Response(200, json={
            "tenant_status": {"active": 3, "pending": 1, "suspended": 0, "rejected": 0, "total": 4},
            "totals": {"tenants": 4, "admins": 5, "apps": 2, "databases": 1, "plans": 3},
            "committed_resources": {"cpu_millicores": 1500, "mem_mb": 1536, "disk_mb": 6144},
            "pending_tenants": [{"slug": "newco", "name": "New Co", "plan_key": ""}],
            "recent_events": [
                {"actor_email": "admin@x", "action": "tenant.approve", "target": "acme",
                 "details": "", "created_at": "2026-06-30T10:00:00+00:00"},
            ],
        })

    monkeypatch.setattr("tetra_cli.cli.client_from_config", lambda require_auth=True: make_client(handler))
    code = main(["admin", "overview"])
    out = capsys.readouterr().out
    assert code == 0
    assert "total=4" in out
    assert "newco" in out          # pending queue rendered
    assert "tenant.approve" in out  # recent activity rendered


def test_client_infra_provision_posts_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/infra/servers"
        assert json.loads(request.content) == {
            "name": "worker-1", "server_type": "cx23", "image": "", "location": "",
        }
        return httpx.Response(200, json={"server": {"id": 42}, "action_status": "success"})

    result = make_client(handler).infra_provision("worker-1", server_type="cx23")
    assert result["server"]["id"] == 42
