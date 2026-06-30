"""tetra — command-line client for Tetra Host (dashboard parity for the terminal)."""

import argparse
import getpass
import os
import sys
from typing import Any

from tetra_cli import __version__
from tetra_cli.client import TetraClient, TetraError
from tetra_cli.config import load_config, save_config


# ── output helpers ────────────────────────────────────────────────────────

def _use_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _use_color() else text


def status_color(value: str) -> str:
    v = (value or "").lower()
    if any(k in v for k in ("fail", "error", "cancel", "exited", "unhealthy")):
        return c(value, "31")  # red
    if any(k in v for k in ("finish", "success", "succeed", "running", "deployed", "active", "connected")):
        return c(value, "32")  # green
    if any(k in v for k in ("build", "progress", "queue", "deploy", "start", "pending", "degraded")):
        return c(value, "33")  # yellow
    return value


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print(c("(none)", "90"))
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(_plain(cell)))
    line = "  ".join(c(h.ljust(widths[i]), "1;90") for i, h in enumerate(headers))
    print(line)
    for row in rows:
        print("  ".join(_pad(cell, widths[i]) for i, cell in enumerate(row)))


def _plain(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i] == "\033":
            while i < len(text) and text[i] != "m":
                i += 1
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _pad(cell: str, width: int) -> str:
    return cell + " " * max(0, width - len(_plain(cell)))


def die(message: str) -> int:
    print(c("error: ", "1;31") + message, file=sys.stderr)
    return 1


def client_from_config(require_auth: bool = True) -> TetraClient:
    cfg = load_config()
    if require_auth and not cfg["token"]:
        raise TetraError("not logged in — run `tetra login` first")
    return TetraClient(cfg["url"], cfg["token"])


# ── command handlers ──────────────────────────────────────────────────────

def cmd_login(args: argparse.Namespace) -> int:
    cfg = load_config()
    url = (args.url or cfg["url"]).rstrip("/")
    email = args.email or input("Email: ").strip()
    password = args.password or getpass.getpass("Password: ")
    client = TetraClient(url)
    client.login(email, password)
    path = save_config(url, client.token)
    admin = client.me()
    print(c("✓", "32") + f" logged in as {admin.get('email')} ({url})")
    print(c(f"  token saved to {path}", "90"))
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    admin = client_from_config().me()
    print(f"{admin.get('full_name')} <{admin.get('email')}>  tenant={admin.get('tenant_slug')}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    data = client_from_config().dashboard()
    m = data.get("metrics", {})
    print(c("Metrics", "1") + f"  projects={m.get('projects')} unhealthy={m.get('unhealthy_projects')} "
          f"mail_domains={m.get('mail_domains')} dns_zones={m.get('dns_zones')} admins={m.get('admins')}")
    rows = [[p["name"], status_color(p["status"]), p.get("detail", "")] for p in data.get("providers", [])]
    print_table(["PROVIDER", "STATUS", "DETAIL"], rows)
    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    projects = client_from_config().projects()
    rows = [[s["id"], s["name"], status_color(s["status"]), s.get("primary_domain", "")] for s in projects]
    print_table(["ID", "NAME", "STATUS", "DOMAIN"], rows)
    return 0


def cmd_deployments(args: argparse.Namespace) -> int:
    deps = client_from_config().deployments(args.project)
    rows = [[d["id"][:16], status_color(d["status"]), (d.get("commit") or "")[:8],
             d.get("branch", ""), d.get("created_at", "")] for d in deps]
    print_table(["DEPLOYMENT", "STATUS", "COMMIT", "BRANCH", "CREATED"], rows)
    return 0


def _follow_logs(client: TetraClient, project: str, deployment_id: str) -> int:
    final = ""
    for event, data in client.stream_logs(project, deployment_id):
        if event == "log":
            stream = data.get("type", "stdout")
            text = data.get("output", "")
            print(c(text, "31") if stream == "stderr" else text)
        elif event == "status":
            print(c(f"-- status: {data.get('status')}", "1;33"))
        elif event == "done":
            final = data.get("status", "")
            print(c(f"-- done: {final}", "1;32" if "fail" not in final.lower() and "error" not in final.lower() else "1;31"))
        elif event == "error":
            return die(data.get("message", "stream error"))
    return 0 if "fail" not in final.lower() and "error" not in final.lower() else 1


def cmd_logs(args: argparse.Namespace) -> int:
    return _follow_logs(client_from_config(), args.project, args.deployment)


def cmd_runtime_logs(args: argparse.Namespace) -> int:
    data = client_from_config().project_runtime_logs(args.project, lines=args.lines)
    logs = data.get("logs", "") if isinstance(data, dict) else str(data)
    print(logs if logs.strip() else c("(no runtime logs)", "90"))
    return 0


def cmd_analytics(args: argparse.Namespace) -> int:
    data = client_from_config().project_analytics(args.project, period=args.period)
    if not data.get("configured"):
        return die("analytics is not configured on this platform (set UMAMI_URL).")
    if not data.get("ready"):
        print(c(data.get("reason", "Analytics is not ready for this project."), "33"))
        return 0
    s = data.get("summary", {})
    print(
        c(f"Analytics ({data.get('period')})", "1")
        + f"  visitors={s.get('visitors')}  pageviews={s.get('pageviews')}"
        f"  bounce={s.get('bounce_rate')}%  avg={s.get('avg_seconds')}s"
    )
    pages = data.get("top_pages", [])
    if pages:
        print_table(
            ["TOP PAGE", "VIEWS"], [[p.get("label", ""), str(p.get("count", 0))] for p in pages]
        )
    refs = data.get("top_referrers", [])
    if refs:
        print_table(
            ["TOP REFERRER", "VISITS"],
            [[r.get("label", ""), str(r.get("count", 0))] for r in refs],
        )
    snippet = data.get("tracking_snippet", "")
    if snippet:
        print(c("\nTracking snippet:", "90"))
        print(snippet)
    return 0


def cmd_errors(args: argparse.Namespace) -> int:
    data = client_from_config().project_errors(args.project)
    if not data.get("configured"):
        return die("error tracking is not configured on this platform (set GLITCHTIP_URL).")
    if not data.get("ready"):
        print(c(data.get("reason", "Error tracking is not ready for this project."), "33"))
        return 0
    issues = data.get("issues", [])
    if not issues:
        print(c("No unresolved issues 🎉", "32"))
    else:
        rows = [
            [
                (i.get("level", "") or "")[:7],
                str(i.get("count", 0)),
                (i.get("title", "") or "")[:60],
            ]
            for i in issues
        ]
        print_table(["LEVEL", "COUNT", "TITLE"], rows)
    dsn = data.get("dsn", "")
    if dsn:
        print(c("\nDSN:", "90") + f" {dsn}")
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    client = client_from_config()
    result = client.deploy(args.project, force=args.force)
    print(c("✓", "32") + " " + str(result.get("message", "Deployment queued.")))
    deployment_id = result.get("deployment_id")
    if deployment_id:
        print(c(f"  deployment {deployment_id}", "90"))
    if args.follow:
        if not deployment_id:
            return die("no deployment id returned; cannot follow logs")
        print(c("-- streaming build logs (ctrl-c to stop) --", "90"))
        return _follow_logs(client, args.project, deployment_id)
    return 0


def cmd_dns_zones(args: argparse.Namespace) -> int:
    data = client_from_config().dns()
    rows = [[z["id"], z["name"], status_color(z.get("status", "")), z.get("account_name", "")]
            for z in data.get("zones", [])]
    print_table(["ZONE ID", "NAME", "STATUS", "ACCOUNT"], rows)
    return 0


def cmd_dns_records(args: argparse.Namespace) -> int:
    data = client_from_config().dns(zone=args.zone)
    rows = [[r["id"][:16], r["type"], r["name"], r.get("content", ""), str(r.get("ttl", ""))]
            for r in data.get("records", [])]
    print_table(["RECORD", "TYPE", "NAME", "CONTENT", "TTL"], rows)
    return 0


def cmd_dns_add(args: argparse.Namespace) -> int:
    client_from_config().dns_add(args.zone, args.type, args.name, args.content, ttl=args.ttl, proxied=args.proxied)
    print(c("✓", "32") + f" {args.type} {args.name} -> {args.content}")
    return 0


def cmd_dns_edit(args: argparse.Namespace) -> int:
    client_from_config().dns_update(
        args.zone,
        args.record,
        args.type,
        args.name,
        args.content,
        ttl=args.ttl,
        proxied=args.proxied,
        priority=args.priority,
    )
    print(c("✓", "32") + f" updated {args.type} {args.name} -> {args.content}")
    return 0


def cmd_dns_rm(args: argparse.Namespace) -> int:
    client_from_config().dns_rm(args.zone, args.record)
    print(c("✓", "32") + f" deleted {args.record}")
    return 0


def cmd_cf_settings(args: argparse.Namespace) -> int:
    data = client_from_config().zone_settings(args.zone)
    print_table(["SETTING", "VALUE"], [[key, status_color(str(value))] for key, value in data.items()])
    return 0


def cmd_cf_set(args: argparse.Namespace) -> int:
    client_from_config().zone_set(args.zone, args.setting, args.value)
    print(c("✓", "32") + f" {args.setting} = {args.value}")
    return 0


def cmd_cf_dnssec(args: argparse.Namespace) -> int:
    client_from_config().zone_dnssec(args.zone, args.status)
    print(c("✓", "32") + f" DNSSEC {args.status}")
    return 0


def cmd_cf_purge(args: argparse.Namespace) -> int:
    client_from_config().zone_purge(args.zone, everything=True)
    print(c("✓", "32") + " cache purge requested")
    return 0


def cmd_cf_analytics(args: argparse.Namespace) -> int:
    data = client_from_config().zone_analytics(args.zone, days=args.days)
    totals = data.get("totals", {})
    print(
        c("Totals", "1")
        + f"  requests={totals.get('requests', 0)} cached={totals.get('cached_requests', 0)} "
        f"bytes={totals.get('bytes', 0)} threats={totals.get('threats', 0)} uniques={totals.get('uniques', 0)}"
    )
    rows = [
        [p.get("date", ""), str(p.get("requests", 0)), str(p.get("cached_requests", 0)),
         str(p.get("threats", 0)), str(p.get("uniques", 0))]
        for p in data.get("points", [])
    ]
    print_table(["DATE", "REQUESTS", "CACHED", "THREATS", "UNIQUES"], rows)
    return 0


def cmd_dns_export(args: argparse.Namespace) -> int:
    data = client_from_config().dns_export(args.zone)
    bind = data.get("bind", "") if isinstance(data, dict) else ""
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(bind)
        count = data.get("record_count", 0) if isinstance(data, dict) else 0
        print(c("✓", "32") + f" exported {count} records -> {args.output}")
    else:
        sys.stdout.write(bind if bind.endswith("\n") or not bind else bind + "\n")
    return 0


def cmd_dns_import(args: argparse.Namespace) -> int:
    try:
        with open(args.file, encoding="utf-8") as handle:
            bind = handle.read()
    except OSError as exc:
        return die(f"cannot read {args.file}: {exc}")
    result = client_from_config().dns_import(args.zone, bind)
    print(c("✓", "32") + " " + str(result.get("message", "records imported") if isinstance(result, dict) else "records imported"))
    return 0


def cmd_env_list(args: argparse.Namespace) -> int:
    envs = client_from_config().envs(args.project)
    rows = [[str(e.get("key", "")), "•••" if not args.reveal else str(e.get("value", "")),
             str(e.get("uuid", e.get("id", "")))] for e in envs]
    print_table(["KEY", "VALUE", "UUID"], rows)
    return 0


def cmd_env_set(args: argparse.Namespace) -> int:
    client_from_config().env_set(args.project, args.key, args.value)
    print(c("✓", "32") + f" {args.key} set")
    return 0


def cmd_env_rm(args: argparse.Namespace) -> int:
    client_from_config().env_rm(args.project, args.uuid)
    print(c("✓", "32") + f" deleted {args.uuid}")
    return 0


def cmd_apps_catalog(args: argparse.Namespace) -> int:
    data = client_from_config().apps_catalog(search=args.search, category=args.category)
    rows = [
        [t["slug"], t.get("name", ""), t.get("category", ""), ", ".join(t.get("tags", [])[:3])]
        for t in data
    ]
    print_table(["SLUG", "NAME", "CATEGORY", "TAGS"], rows)
    print(c(f"  {len(data)} apps", "90"))
    return 0


def cmd_apps_list(args: argparse.Namespace) -> int:
    data = client_from_config().apps()
    rows = [
        [a["project"], a.get("name", ""), status_color(a.get("status", "unknown")), a.get("domain", "")]
        for a in data
    ]
    print_table(["PROJECT", "NAME", "STATUS", "DOMAIN"], rows)
    return 0


def cmd_apps_install(args: argparse.Namespace) -> int:
    result = client_from_config().apps_install(args.slug, name=args.name, domain=args.domain)
    project = result.get("project", "") if isinstance(result, dict) else ""
    print(c("✓", "32") + f" {result.get('message', 'installed') if isinstance(result, dict) else 'installed'}"
          + (f"  project={project}" if project else ""))
    if isinstance(result, dict) and result.get("domain"):
        print(c(f"  {result['domain']}", "90"))
    return 0


def cmd_apps_start(args: argparse.Namespace) -> int:
    client_from_config().apps_start(args.project)
    print(c("✓", "32") + f" started {args.project}")
    return 0


def cmd_apps_stop(args: argparse.Namespace) -> int:
    client_from_config().apps_stop(args.project)
    print(c("✓", "32") + f" stopped {args.project}")
    return 0


def cmd_apps_rm(args: argparse.Namespace) -> int:
    client_from_config().apps_rm(args.project, volumes=args.volumes)
    print(c("✓", "32") + f" removed {args.project}")
    return 0


def cmd_apps_logs(args: argparse.Namespace) -> int:
    result = client_from_config().apps_logs(args.project)
    print(result.get("logs", "") if isinstance(result, dict) else result)
    return 0


def cmd_plans_list(args: argparse.Namespace) -> int:
    plans = client_from_config().plans(include_archived=args.include_archived)
    rows = [
        [
            str(p.get("id", "")),
            p.get("key", ""),
            p.get("name", ""),
            f"{p.get('price_cents', 0) / 100:.2f} {p.get('currency', '')}",
            str(p.get("max_apps", "")),
            str(p.get("max_domains", "")),
            c("archived", "31") if p.get("is_archived") else c("active", "32"),
        ]
        for p in plans
    ]
    print_table(["ID", "KEY", "NAME", "PRICE", "MAX APPS", "MAX DOMAINS", "STATUS"], rows)
    return 0


def cmd_plans_create(args: argparse.Namespace) -> int:
    fields: dict = {
        "key": args.key,
        "name": args.name,
        "price_cents": args.price_cents,
        "currency": args.currency,
        "max_apps": args.max_apps,
        "max_domains": args.max_domains,
    }
    if args.description is not None:
        fields["description"] = args.description
    if args.cpu_millicores is not None:
        fields["cpu_millicores"] = args.cpu_millicores
    if args.mem_mb is not None:
        fields["mem_mb"] = args.mem_mb
    if args.disk_mb is not None:
        fields["disk_mb"] = args.disk_mb
    if args.sort_order is not None:
        fields["sort_order"] = args.sort_order
    plan = client_from_config().plan_create(**fields)
    print(c("✓", "32") + f" plan created: {plan.get('key')} (id={plan.get('id')})")
    return 0


def cmd_plans_edit(args: argparse.Namespace) -> int:
    fields: dict = {}
    for attr in ("name", "description", "price_cents", "currency", "max_apps", "max_domains",
                 "cpu_millicores", "mem_mb", "disk_mb", "sort_order"):
        val = getattr(args, attr, None)
        if val is not None:
            fields[attr] = val
    if not fields:
        return die("no fields provided — use --name, --price-cents, etc.")
    plan = client_from_config().plan_update(args.plan_id, **fields)
    print(c("✓", "32") + f" plan {args.plan_id} updated")
    if isinstance(plan, dict) and plan.get("name"):
        print(c(f"  name={plan['name']}", "90"))
    return 0


def cmd_plans_archive(args: argparse.Namespace) -> int:
    client_from_config().plan_archive(args.plan_id)
    print(c("✓", "32") + f" plan {args.plan_id} archived")
    return 0


def cmd_tenants_list(args: argparse.Namespace) -> int:
    tenants = client_from_config().tenants()
    rows = [
        [
            t.get("slug", ""),
            t.get("name", ""),
            status_color(t.get("status", "")),
            t.get("plan_key", "") or "",
        ]
        for t in tenants
    ]
    print_table(["SLUG", "NAME", "STATUS", "PLAN"], rows)
    return 0


def _cmd_tenant_action(action: str, args: argparse.Namespace) -> int:
    result = client_from_config().tenant_action(args.slug, action)
    slug = result.get("slug", args.slug) if isinstance(result, dict) else args.slug
    status = result.get("status", "") if isinstance(result, dict) else ""
    past = {"approve": "approved", "reject": "rejected", "suspend": "suspended", "reactivate": "reactivated"}
    print(
        c("✓", "32")
        + f" tenant {slug} {past.get(action, action)}"
        + (f"  status={status_color(status)}" if status else "")
    )
    return 0


def cmd_tenants_approve(args: argparse.Namespace) -> int:
    return _cmd_tenant_action("approve", args)


def cmd_tenants_reject(args: argparse.Namespace) -> int:
    return _cmd_tenant_action("reject", args)


def cmd_tenants_suspend(args: argparse.Namespace) -> int:
    return _cmd_tenant_action("suspend", args)


def cmd_tenants_reactivate(args: argparse.Namespace) -> int:
    return _cmd_tenant_action("reactivate", args)


def cmd_admin_overview(args: argparse.Namespace) -> int:
    data = client_from_config().admin_overview()
    ts = data.get("tenant_status", {})
    tot = data.get("totals", {})
    res = data.get("committed_resources", {})
    print(
        c("Tenants", "1")
        + f"  total={ts.get('total')}  active={ts.get('active')}  pending={ts.get('pending')}"
        f"  suspended={ts.get('suspended')}  rejected={ts.get('rejected')}"
    )
    print(
        c("Totals", "1")
        + f"  admins={tot.get('admins')}  apps={tot.get('apps')}"
        f"  databases={tot.get('databases')}  plans={tot.get('plans')}"
    )
    print(
        c("Committed", "1")
        + f"  cpu={res.get('cpu_millicores')}m  mem={res.get('mem_mb')}MB  disk={res.get('disk_mb')}MB"
    )

    pending = data.get("pending_tenants", [])
    if pending:
        print(c("\nPending approval", "33"))
        rows = [[t.get("slug", ""), t.get("name", ""), t.get("plan_key", "") or ""] for t in pending]
        print_table(["SLUG", "NAME", "PLAN"], rows)

    events = data.get("recent_events", [])
    if events:
        print(c("\nRecent activity", "1"))
        rows = [
            [
                (e.get("created_at", "") or "")[:19],
                e.get("action", ""),
                e.get("actor_email", ""),
                e.get("target", ""),
            ]
            for e in events
        ]
        print_table(["WHEN", "ACTION", "ACTOR", "TARGET"], rows)
    return 0


def cmd_usage(args: argparse.Namespace) -> int:
    data = client_from_config().usage()
    plan = data.get("plan_key", "") or "free"
    print(c(f"Plan: {plan}", "1"))
    rows = [
        ["apps", f"{data.get('apps_used', 0)}/{data.get('apps_limit', 0)}", "enforced"],
        ["cpu", f"{data.get('cpu_millicores_used', 0)}/{data.get('cpu_millicores_limit', 0)} mc", "advisory"],
        ["mem", f"{data.get('mem_mb_used', 0)}/{data.get('mem_mb_limit', 0)} MB", "advisory"],
        ["disk", f"{data.get('disk_mb_used', 0)}/{data.get('disk_mb_limit', 0)} MB", "advisory"],
        ["domains", f"{data.get('domains_used', 0)}/{data.get('domains_limit', 0)}", "advisory"],
    ]
    print_table(["RESOURCE", "USED/LIMIT", "STATUS"], rows)
    return 0


def cmd_databases_list(args: argparse.Namespace) -> int:
    dbs = client_from_config().databases()
    rows = [
        [
            d.get("uuid", d.get("id", "")),
            d.get("name", ""),
            d.get("type", ""),
            status_color(d.get("status", "")),
            d.get("server_name", ""),
        ]
        for d in dbs
    ]
    print_table(["UUID", "NAME", "TYPE", "STATUS", "SERVER"], rows)
    return 0


def cmd_databases_provision(args: argparse.Namespace) -> int:
    result = client_from_config().provision_database(
        args.type,
        args.name,
        args.server_uuid,
        args.project_uuid,
        args.environment,
    )
    uuid = result.get("uuid", result.get("id", "")) if isinstance(result, dict) else ""
    print(c("✓", "32") + " database provisioned"
          + (f"  uuid={uuid}" if uuid else "")
          + (f"  name={args.name}" if args.name else ""))
    return 0


def cmd_databases_backups(args: argparse.Namespace) -> int:
    backups = client_from_config().database_backups(args.uuid)
    rows = [
        [
            b.get("uuid", b.get("id", "")),
            status_color(b.get("status", "")),
            b.get("created_at", ""),
            b.get("size", ""),
        ]
        for b in backups
    ]
    print_table(["UUID", "STATUS", "CREATED", "SIZE"], rows)
    return 0


def cmd_databases_backup(args: argparse.Namespace) -> int:
    result = client_from_config().create_database_backup(args.uuid)
    msg = result.get("message", "Backup queued.") if isinstance(result, dict) else "Backup queued."
    print(c("✓", "32") + " " + str(msg))
    return 0


def cmd_deploys_git(args: argparse.Namespace) -> int:
    import time

    client = client_from_config()
    start = client.deploy_git(args.git_url, name=args.name, ref=args.ref, port=args.port)
    deployment_id = start.get("deployment_id", "") if isinstance(start, dict) else ""
    if not deployment_id:
        return die("deploy did not start")
    print(c(f"-- building {args.name} (deployment {deployment_id[:8]}) --", "90"))
    seen = 0
    while True:
        status = client.deploy_status(deployment_id)
        lines = (status.get("log", "") or "").splitlines()
        for line in lines[seen:]:
            print(line)
        seen = len(lines)
        state = status.get("status", "")
        if state == "ready":
            domain = status.get("domain", "")
            print(c("✓ deployed", "1;32") + (c(f"  https://{domain}", "90") if domain else ""))
            return 0
        if state == "error":
            return die(status.get("error", "build failed"))
        time.sleep(2)


# ── parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tetra", description="Tetra Host CLI — dashboard parity for the terminal.")
    p.add_argument("--version", action="version", version=f"tetra-cli {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("login", help="authenticate and store a token")
    sp.add_argument("--url")
    sp.add_argument("--email")
    sp.add_argument("--password")
    sp.set_defaults(func=cmd_login)

    sub.add_parser("whoami", help="show the current admin").set_defaults(func=cmd_whoami)
    sub.add_parser("dashboard", help="show platform metrics").set_defaults(func=cmd_dashboard)
    sub.add_parser("usage", help="show quota usage vs plan limits").set_defaults(func=cmd_usage)
    sub.add_parser("projects", help="list projects").set_defaults(func=cmd_projects)

    sp = sub.add_parser("deploy", help="trigger a deployment")
    sp.add_argument("project")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("-f", "--follow", action="store_true", help="stream build logs after deploying")
    sp.set_defaults(func=cmd_deploy)

    sp = sub.add_parser("deployments", help="list deployments for a project")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_deployments)

    sp = sub.add_parser("logs", help="stream build logs for a deployment")
    sp.add_argument("project")
    sp.add_argument("deployment")
    sp.set_defaults(func=cmd_logs)

    sp = sub.add_parser("runtime-logs", help="show a project's live container (runtime) logs")
    sp.add_argument("project")
    sp.add_argument("--lines", type=int, default=200)
    sp.set_defaults(func=cmd_runtime_logs)

    sp = sub.add_parser("analytics", help="show a project's web analytics (Umami)")
    sp.add_argument("project")
    sp.add_argument("--period", default="7d", choices=["24h", "7d", "30d", "90d"])
    sp.set_defaults(func=cmd_analytics)

    sp = sub.add_parser("errors", help="show a project's unresolved errors (GlitchTip)")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_errors)

    dns = sub.add_parser("dns", help="manage DNS").add_subparsers(dest="dns_cmd", required=True)
    dns.add_parser("zones", help="list zones").set_defaults(func=cmd_dns_zones)
    sp = dns.add_parser("records", help="list records in a zone")
    sp.add_argument("zone")
    sp.set_defaults(func=cmd_dns_records)
    sp = dns.add_parser("add", help="create a record")
    sp.add_argument("zone")
    sp.add_argument("type")
    sp.add_argument("name")
    sp.add_argument("content")
    sp.add_argument("--ttl", type=int, default=1)
    sp.add_argument("--proxied", action="store_true")
    sp.set_defaults(func=cmd_dns_add)
    sp = dns.add_parser("edit", help="update a record")
    sp.add_argument("zone")
    sp.add_argument("record")
    sp.add_argument("type")
    sp.add_argument("name")
    sp.add_argument("content")
    sp.add_argument("--ttl", type=int, default=1)
    sp.add_argument("--proxied", action="store_true")
    sp.add_argument("--priority", type=int, default=None)
    sp.set_defaults(func=cmd_dns_edit)
    sp = dns.add_parser("rm", help="delete a record")
    sp.add_argument("zone")
    sp.add_argument("record")
    sp.set_defaults(func=cmd_dns_rm)
    sp = dns.add_parser("export", help="export a zone as a BIND file")
    sp.add_argument("zone")
    sp.add_argument("-o", "--output", help="write to a file instead of stdout")
    sp.set_defaults(func=cmd_dns_export)
    sp = dns.add_parser("import", help="import a BIND file into a zone")
    sp.add_argument("zone")
    sp.add_argument("file")
    sp.set_defaults(func=cmd_dns_import)

    env = sub.add_parser("env", help="manage project env vars").add_subparsers(dest="env_cmd", required=True)
    sp = env.add_parser("list", help="list env vars")
    sp.add_argument("project")
    sp.add_argument("--reveal", action="store_true")
    sp.set_defaults(func=cmd_env_list)
    sp = env.add_parser("set", help="create/update an env var")
    sp.add_argument("project")
    sp.add_argument("key")
    sp.add_argument("value")
    sp.set_defaults(func=cmd_env_set)
    sp = env.add_parser("rm", help="delete an env var")
    sp.add_argument("project")
    sp.add_argument("uuid")
    sp.set_defaults(func=cmd_env_rm)

    _db_types = ["postgresql", "mysql", "mariadb", "mongodb", "redis", "keydb", "dragonfly", "clickhouse"]
    databases = sub.add_parser("databases", help="manage databases").add_subparsers(
        dest="databases_cmd", required=True
    )
    databases.add_parser("list", help="list databases").set_defaults(func=cmd_databases_list)
    sp = databases.add_parser("provision", help="provision a new database")
    sp.add_argument("type", choices=_db_types, help="database type")
    sp.add_argument("name", help="database name")
    sp.add_argument("--server-uuid", dest="server_uuid", required=True, help="Coolify server UUID")
    sp.add_argument("--project-uuid", dest="project_uuid", required=True, help="Coolify project UUID")
    sp.add_argument("--environment", default="production", help="environment name (default: production)")
    sp.set_defaults(func=cmd_databases_provision)
    sp = databases.add_parser("backups", help="list backups for a database")
    sp.add_argument("uuid", help="database UUID")
    sp.set_defaults(func=cmd_databases_backups)
    sp = databases.add_parser("backup", help="create a backup for a database")
    sp.add_argument("uuid", help="database UUID")
    sp.set_defaults(func=cmd_databases_backup)

    cf = sub.add_parser("cf", help="Cloudflare zone tools").add_subparsers(dest="cf_cmd", required=True)
    sp = cf.add_parser("settings", help="show zone settings")
    sp.add_argument("zone")
    sp.set_defaults(func=cmd_cf_settings)
    sp = cf.add_parser("set", help="update a zone setting (e.g. ssl full)")
    sp.add_argument("zone")
    sp.add_argument("setting")
    sp.add_argument("value")
    sp.set_defaults(func=cmd_cf_set)
    sp = cf.add_parser("dnssec", help="set DNSSEC status (active|disabled)")
    sp.add_argument("zone")
    sp.add_argument("status")
    sp.set_defaults(func=cmd_cf_dnssec)
    sp = cf.add_parser("purge", help="purge the zone cache")
    sp.add_argument("zone")
    sp.set_defaults(func=cmd_cf_purge)
    sp = cf.add_parser("analytics", help="show zone HTTP analytics")
    sp.add_argument("zone")
    sp.add_argument("--days", type=int, default=7)
    sp.set_defaults(func=cmd_cf_analytics)

    apps = sub.add_parser("apps", help="install & control pre-defined Docker apps").add_subparsers(
        dest="apps_cmd", required=True
    )
    sp = apps.add_parser("catalog", help="browse the app marketplace")
    sp.add_argument("--search")
    sp.add_argument("--category")
    sp.set_defaults(func=cmd_apps_catalog)
    apps.add_parser("list", help="list installed apps").set_defaults(func=cmd_apps_list)
    sp = apps.add_parser("install", help="install an app (e.g. wordpress-with-mariadb)")
    sp.add_argument("slug")
    sp.add_argument("--name")
    sp.add_argument("--domain")
    sp.set_defaults(func=cmd_apps_install)
    sp = apps.add_parser("start", help="start an installed app")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_apps_start)
    sp = apps.add_parser("stop", help="stop an installed app")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_apps_stop)
    sp = apps.add_parser("rm", help="remove an installed app")
    sp.add_argument("project")
    sp.add_argument("--volumes", action="store_true", help="also delete volumes (data loss)")
    sp.set_defaults(func=cmd_apps_rm)
    sp = apps.add_parser("logs", help="show an app's logs")
    sp.add_argument("project")
    sp.set_defaults(func=cmd_apps_logs)

    deploys = sub.add_parser("deploys", help="build & deploy git repos").add_subparsers(
        dest="deploys_cmd", required=True
    )
    sp = deploys.add_parser("git", help="build and deploy a git repo (Dockerfile or Nixpacks)")
    sp.add_argument("git_url")
    sp.add_argument("--name", required=True)
    sp.add_argument("--ref", default="main")
    sp.add_argument("--port", type=int, default=3000)
    sp.set_defaults(func=cmd_deploys_git)

    plans = sub.add_parser("plans", help="manage subscription plans (platform-admin)").add_subparsers(
        dest="plans_cmd", required=True
    )
    sp = plans.add_parser("list", help="list plans")
    sp.add_argument("--include-archived", dest="include_archived", action="store_true",
                    help="include archived plans")
    sp.set_defaults(func=cmd_plans_list)
    sp = plans.add_parser("create", help="create a plan")
    sp.add_argument("key", help="unique machine key (e.g. starter)")
    sp.add_argument("name", help="display name")
    sp.add_argument("--price-cents", dest="price_cents", type=int, required=True)
    sp.add_argument("--currency", default="USD")
    sp.add_argument("--max-apps", dest="max_apps", type=int, required=True)
    sp.add_argument("--max-domains", dest="max_domains", type=int, required=True)
    sp.add_argument("--description")
    sp.add_argument("--cpu-millicores", dest="cpu_millicores", type=int, default=None)
    sp.add_argument("--mem-mb", dest="mem_mb", type=int, default=None)
    sp.add_argument("--disk-mb", dest="disk_mb", type=int, default=None)
    sp.add_argument("--sort-order", dest="sort_order", type=int, default=None)
    sp.set_defaults(func=cmd_plans_create)
    sp = plans.add_parser("edit", help="update a plan (only flags provided are sent)")
    sp.add_argument("plan_id", help="plan ID")
    sp.add_argument("--name")
    sp.add_argument("--description")
    sp.add_argument("--price-cents", dest="price_cents", type=int, default=None)
    sp.add_argument("--currency")
    sp.add_argument("--max-apps", dest="max_apps", type=int, default=None)
    sp.add_argument("--max-domains", dest="max_domains", type=int, default=None)
    sp.add_argument("--cpu-millicores", dest="cpu_millicores", type=int, default=None)
    sp.add_argument("--mem-mb", dest="mem_mb", type=int, default=None)
    sp.add_argument("--disk-mb", dest="disk_mb", type=int, default=None)
    sp.add_argument("--sort-order", dest="sort_order", type=int, default=None)
    sp.set_defaults(func=cmd_plans_edit)
    sp = plans.add_parser("archive", help="archive a plan")
    sp.add_argument("plan_id", help="plan ID")
    sp.set_defaults(func=cmd_plans_archive)

    tenants = sub.add_parser("tenants", help="manage tenants (platform-admin)").add_subparsers(
        dest="tenants_cmd", required=True
    )
    tenants.add_parser("list", help="list all tenants").set_defaults(func=cmd_tenants_list)
    for _action, _help in (
        ("approve", "approve a pending tenant"),
        ("reject", "reject a pending tenant"),
        ("suspend", "suspend an active tenant"),
        ("reactivate", "reactivate a suspended tenant"),
    ):
        _sp = tenants.add_parser(_action, help=_help)
        _sp.add_argument("slug", help="tenant slug")
        _sp.set_defaults(func=globals()[f"cmd_tenants_{_action}"])

    admin = sub.add_parser("admin", help="platform operator tools (platform-admin)").add_subparsers(
        dest="admin_cmd", required=True
    )
    admin.add_parser(
        "overview", help="platform command center: counts, pending approvals, recent activity"
    ).set_defaults(func=cmd_admin_overview)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result: Any = args.func(args)
        return int(result or 0)
    except TetraError as exc:
        suffix = f" (HTTP {exc.status})" if exc.status else ""
        return die(f"{exc}{suffix}")
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
