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
    print(c("Metrics", "1") + f"  sites={m.get('sites')} unhealthy={m.get('unhealthy_sites')} "
          f"mail_domains={m.get('mail_domains')} dns_zones={m.get('dns_zones')} admins={m.get('admins')}")
    rows = [[p["name"], status_color(p["status"]), p.get("detail", "")] for p in data.get("providers", [])]
    print_table(["PROVIDER", "STATUS", "DETAIL"], rows)
    return 0


def cmd_sites(args: argparse.Namespace) -> int:
    sites = client_from_config().sites()
    rows = [[s["id"], s["name"], status_color(s["status"]), s.get("primary_domain", "")] for s in sites]
    print_table(["ID", "NAME", "STATUS", "DOMAIN"], rows)
    return 0


def cmd_deployments(args: argparse.Namespace) -> int:
    deps = client_from_config().deployments(args.site)
    rows = [[d["id"][:16], status_color(d["status"]), (d.get("commit") or "")[:8],
             d.get("branch", ""), d.get("created_at", "")] for d in deps]
    print_table(["DEPLOYMENT", "STATUS", "COMMIT", "BRANCH", "CREATED"], rows)
    return 0


def _follow_logs(client: TetraClient, site: str, deployment_id: str) -> int:
    final = ""
    for event, data in client.stream_logs(site, deployment_id):
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
    return _follow_logs(client_from_config(), args.site, args.deployment)


def cmd_deploy(args: argparse.Namespace) -> int:
    client = client_from_config()
    result = client.deploy(args.site, force=args.force)
    print(c("✓", "32") + " " + str(result.get("message", "Deployment queued.")))
    deployment_id = result.get("deployment_id")
    if deployment_id:
        print(c(f"  deployment {deployment_id}", "90"))
    if args.follow:
        if not deployment_id:
            return die("no deployment id returned; cannot follow logs")
        print(c("-- streaming build logs (ctrl-c to stop) --", "90"))
        return _follow_logs(client, args.site, deployment_id)
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
    envs = client_from_config().envs(args.site)
    rows = [[str(e.get("key", "")), "•••" if not args.reveal else str(e.get("value", "")),
             str(e.get("uuid", e.get("id", "")))] for e in envs]
    print_table(["KEY", "VALUE", "UUID"], rows)
    return 0


def cmd_env_set(args: argparse.Namespace) -> int:
    client_from_config().env_set(args.site, args.key, args.value)
    print(c("✓", "32") + f" {args.key} set")
    return 0


def cmd_env_rm(args: argparse.Namespace) -> int:
    client_from_config().env_rm(args.site, args.uuid)
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


def cmd_deploys_git(args: argparse.Namespace) -> int:
    result = client_from_config().deploy_git(args.git_url, name=args.name, ref=args.ref, port=args.port)
    builder = result.get("builder", "") if isinstance(result, dict) else ""
    print(c("✓", "32") + f" deployed {result.get('project')}" + (f" ({builder})" if builder else ""))
    if isinstance(result, dict) and result.get("domain"):
        print(c(f"  https://{result['domain']}", "90"))
    return 0


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
    sub.add_parser("sites", help="list sites").set_defaults(func=cmd_sites)

    sp = sub.add_parser("deploy", help="trigger a deployment")
    sp.add_argument("site")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("-f", "--follow", action="store_true", help="stream build logs after deploying")
    sp.set_defaults(func=cmd_deploy)

    sp = sub.add_parser("deployments", help="list deployments for a site")
    sp.add_argument("site")
    sp.set_defaults(func=cmd_deployments)

    sp = sub.add_parser("logs", help="stream build logs for a deployment")
    sp.add_argument("site")
    sp.add_argument("deployment")
    sp.set_defaults(func=cmd_logs)

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

    env = sub.add_parser("env", help="manage site env vars").add_subparsers(dest="env_cmd", required=True)
    sp = env.add_parser("list", help="list env vars")
    sp.add_argument("site")
    sp.add_argument("--reveal", action="store_true")
    sp.set_defaults(func=cmd_env_list)
    sp = env.add_parser("set", help="create/update an env var")
    sp.add_argument("site")
    sp.add_argument("key")
    sp.add_argument("value")
    sp.set_defaults(func=cmd_env_set)
    sp = env.add_parser("rm", help="delete an env var")
    sp.add_argument("site")
    sp.add_argument("uuid")
    sp.set_defaults(func=cmd_env_rm)

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
