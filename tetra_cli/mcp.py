"""Tetra MCP server — the platform's third surface (dashboard ↔ CLI ↔ MCP parity).

Implements the Model Context Protocol's stdio transport by hand — JSON-RPC 2.0,
one message per line — so the CLI keeps its no-new-dependencies rule. Every tool
is a thin, typed wrapper over the same ``/api/v1`` contract the dashboard and CLI
use (via :class:`TetraClient`), so an AI agent sees exactly what a human sees.

Safety model (writes are human-gated):
- Read tools are always listed and callable.
- Write tools exist only when the operator starts the server with
  ``tetra mcp serve --allow-writes``, and every write call must ALSO pass
  ``confirm=true`` — two explicit human decisions before anything changes.
- Billable/platform-admin operations (Hetzner provisioning, plans, tenants) and
  DNS writes are deliberately NOT exposed at all.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from tetra_cli.client import TetraClient, TetraError

PROTOCOL_VERSION = "2025-06-18"
_SERVER_INFO = {"name": "tetra-mcp", "version": "1.0.0"}

_CONFIRM = {
    "confirm": {
        "type": "boolean",
        "description": "Must be true. Ask the human operator before setting it.",
    }
}


def _schema(properties: dict[str, dict] | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties or {}, "required": required or []}


def _project_arg(description: str) -> dict[str, dict]:
    return {"project": {"type": "string", "description": description}}


_TOOLS: list[dict[str, Any]] = [
    # ── Reads (always available) ───────────────────────────────────────────
    {
        "name": "list_apps",
        "description": "List the tenant's deployed apps (native Tetra Engine inventory) with status and domain.",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.apps(),
    },
    {
        "name": "list_deployments",
        "description": "Recent native deployments (builds) with status, ref, image and domain.",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.native_deploys(),
    },
    {
        "name": "get_deployment",
        "description": "One deployment's full status + build log — use it to explain why a build failed.",
        "inputSchema": _schema(
            {"deployment_id": {"type": "string", "description": "Deployment id"}},
            ["deployment_id"],
        ),
        "write": False,
        "handler": lambda c, a: c.deploy_status(a["deployment_id"]),
    },
    {
        "name": "explain_deployment",
        "description": "Diagnose a deployment's build/run outcome and get suggested fixes "
                       "(heuristic analysis, AI-enriched when configured) — use this to explain a failed build.",
        "inputSchema": _schema(
            {"deployment_id": {"type": "string", "description": "Deployment id"}},
            ["deployment_id"],
        ),
        "write": False,
        "handler": lambda c, a: c.explain_deployment(a["deployment_id"]),
    },
    {
        "name": "explain_error",
        "description": "Diagnose a captured runtime error (from the Errors tab) and get suggested "
                       "fixes (heuristic analysis, AI-enriched when configured). Needs the app id "
                       "and the GlitchTip issue id.",
        "inputSchema": _schema(
            {
                "application_id": {"type": "string", "description": "App/project id"},
                "issue_id": {"type": "string", "description": "GlitchTip issue id"},
            },
            ["application_id", "issue_id"],
        ),
        "write": False,
        "handler": lambda c, a: c.explain_error(a["application_id"], a["issue_id"]),
    },
    {
        "name": "list_api_tokens",
        "description": "List the caller's personal API tokens (metadata only — no secrets). "
                       "Creating/revoking tokens is deliberately human-only (secret reveal + "
                       "account security), so those are not exposed here.",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.list_tokens(),
    },
    {
        "name": "two_factor_status",
        "description": "Whether the caller's account has TOTP two-factor auth enabled (and how "
                       "many backup codes remain). Enabling/disabling 2FA is deliberately "
                       "human-only (authenticator enrollment + password re-verification).",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.two_factor_status(),
    },
    {
        "name": "list_notification_channels",
        "description": "List the tenant's outbound webhook notification channels (name, url, "
                       "subscribed events, last delivery status — no secrets). Creating/deleting "
                       "and test-sends are human-only.",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.list_notifications(),
    },
    {
        "name": "app_logs",
        "description": "Runtime container logs for an app.",
        "inputSchema": _schema(_project_arg("App/project name"), ["project"]),
        "write": False,
        "handler": lambda c, a: c.apps_logs(a["project"]),
    },
    {
        "name": "app_compute",
        "description": "Live CPU/memory/network samples for an app's containers.",
        "inputSchema": _schema(_project_arg("App/project name"), ["project"]),
        "write": False,
        "handler": lambda c, a: c.apps_compute(a["project"]),
    },
    {
        "name": "list_previews",
        "description": "Per-branch preview environments (their branch, stack and URL).",
        "inputSchema": _schema(_project_arg("Optional app/project filter")),
        "write": False,
        "handler": lambda c, a: c.previews(project=a.get("project")),
    },
    {
        "name": "list_domains",
        "description": "Custom domains with verification status and the DNS records to set.",
        "inputSchema": _schema(_project_arg("Optional app/project filter")),
        "write": False,
        "handler": lambda c, a: c.domains(project=a.get("project")),
    },
    {
        "name": "usage",
        "description": "The tenant's plan usage/quota summary (apps, cpu, memory, disk).",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.usage(),
    },
    # ── Writes (need --allow-writes AND confirm=true) ──────────────────────
    {
        "name": "deploy_git",
        "description": "Build a git repository and deploy it as a new app (async; returns the deployment id).",
        "inputSchema": _schema(
            {
                "git_url": {"type": "string", "description": "Repository URL"},
                "name": {"type": "string", "description": "App name"},
                "ref": {"type": "string", "description": "Branch (default main)"},
                "port": {"type": "integer", "description": "App port (default 3000)"},
                **_CONFIRM,
            },
            ["git_url", "name", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.deploy_git(
            a["git_url"], a["name"], ref=a.get("ref", "main"), port=int(a.get("port", 3000))
        ),
    },
    {
        "name": "rollback_deployment",
        "description": "Instant rollback: redeploy a prior successful deployment's image (no rebuild).",
        "inputSchema": _schema(
            {"deployment_id": {"type": "string", "description": "The deployment to roll back to"},
             **_CONFIRM},
            ["deployment_id", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.rollback_deploy(a["deployment_id"]),
    },
    {
        "name": "teardown_preview",
        "description": "Tear down a preview environment (its stack and URL).",
        "inputSchema": _schema(
            {"preview_id": {"type": "string", "description": "Preview id from list_previews"},
             **_CONFIRM},
            ["preview_id", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.delete_preview(a["preview_id"]),
    },
    {
        "name": "set_env_var",
        "description": "Set an app environment variable (encrypted at rest; applied on next deploy).",
        "inputSchema": _schema(
            {
                **_project_arg("App/project name"),
                "key": {"type": "string"},
                "value": {"type": "string"},
                "is_secret": {"type": "boolean", "description": "Mask the value in listings"},
                **_CONFIRM,
            },
            ["project", "key", "value", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.deploy_env_set(
            a["project"], a["key"], a["value"], is_secret=bool(a.get("is_secret", False))
        ),
    },
    {
        "name": "mail_overview",
        "description": "List the tenant's mail domains and mailboxes (Mailcow inventory).",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.mail(),
    },
    {
        "name": "list_mail_aliases",
        "description": "List the tenant's mail aliases.",
        "inputSchema": _schema(),
        "write": False,
        "handler": lambda c, a: c.mail_aliases(),
    },
    {
        "name": "get_mail_dkim",
        "description": "Get the DKIM DNS record (name + TXT content) for a mail domain.",
        "inputSchema": _schema(
            {"domain": {"type": "string", "description": "Mail domain"}}, ["domain"]
        ),
        "write": False,
        "handler": lambda c, a: c.mail_dkim(a["domain"]),
    },
    {
        "name": "create_mail_domain",
        "description": "Create a mail domain — provisions DKIM and MX/SPF/DMARC DNS automatically.",
        "inputSchema": _schema(
            {
                "domain": {"type": "string", "description": "Fully qualified mail domain"},
                "description": {"type": "string"},
                **_CONFIRM,
            },
            ["domain", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.create_mail_domain(
            a["domain"], description=str(a.get("description", ""))
        ),
    },
    {
        "name": "delete_mail_domain",
        "description": "Delete a mail domain and unregister its mailboxes (DNS records are kept).",
        "inputSchema": _schema(
            {"domain": {"type": "string", "description": "Mail domain"}, **_CONFIRM},
            ["domain", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.delete_mail_domain(a["domain"]),
    },
    {
        "name": "create_mail_alias",
        "description": "Create a mail alias (address → goto) on a domain the tenant owns.",
        "inputSchema": _schema(
            {
                "address": {"type": "string", "description": "Alias address (or @domain catchall)"},
                "goto": {"type": "string", "description": "Destination address(es), comma-separated"},
                **_CONFIRM,
            },
            ["address", "goto", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.create_mail_alias(a["address"], a["goto"]),
    },
    {
        "name": "delete_mail_alias",
        "description": "Delete a mail alias by id.",
        "inputSchema": _schema(
            {"alias_id": {"type": "integer", "description": "Alias id"}, **_CONFIRM},
            ["alias_id", "confirm"],
        ),
        "write": True,
        "handler": lambda c, a: c.delete_mail_alias(int(a["alias_id"])),
    },
    # Mailbox creation is deliberately NOT exposed over MCP: it would put a mailbox
    # password into the model's context/transcript. Use `tetra mail mailbox add`.
]


def _tool_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


class MCPServer:
    """Protocol-pure MCP message handler; transport lives in :func:`serve_stdio`."""

    def __init__(self, client: TetraClient, *, allow_writes: bool = False) -> None:
        self.client = client
        self.allow_writes = allow_writes

    def visible_tools(self) -> list[dict]:
        return [tool for tool in _TOOLS if self.allow_writes or not tool["write"]]

    def handle_message(self, message: dict) -> dict | None:
        """Handle one JSON-RPC message; returns the response, or None for notifications."""
        method = message.get("method", "")
        message_id = message.get("id")
        if message_id is None:  # notifications (e.g. notifications/initialized) get no reply
            return None
        if method == "initialize":
            params = message.get("params") or {}
            requested = params.get("protocolVersion")
            return self._result(message_id, {
                "protocolVersion": requested if isinstance(requested, str) and requested else PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": _SERVER_INFO,
            })
        if method == "ping":
            return self._result(message_id, {})
        if method == "tools/list":
            return self._result(message_id, {
                "tools": [
                    {"name": t["name"], "description": t["description"],
                     "inputSchema": t["inputSchema"]}
                    for t in self.visible_tools()
                ]
            })
        if method == "tools/call":
            params = message.get("params") or {}
            return self._result(
                message_id, self._call(params.get("name", ""), params.get("arguments") or {})
            )
        return {
            "jsonrpc": "2.0", "id": message_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    @staticmethod
    def _result(message_id: Any, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": message_id, "result": result}

    def _call(self, name: str, arguments: dict) -> dict:
        tool = next((t for t in _TOOLS if t["name"] == name), None)
        if tool is None:
            return _tool_error(f"Unknown tool: {name}")
        if tool["write"]:
            if not self.allow_writes:
                return _tool_error(
                    "Write tools are disabled on this server — the operator must restart it "
                    "with `tetra mcp serve --allow-writes` to enable them."
                )
            if arguments.get("confirm") is not True:
                return _tool_error(
                    "This tool changes live infrastructure. Get the human operator's approval, "
                    "then re-call it with confirm=true."
                )
        try:
            payload = tool["handler"](self.client, arguments)
        except TetraError as exc:
            return _tool_error(str(exc))
        except KeyError as exc:
            return _tool_error(f"Missing required argument: {exc.args[0]}")
        except (ValueError, TypeError) as exc:
            # Bad-typed arguments (e.g. a non-numeric alias_id) must come back as a
            # tool error, not kill the stdio loop.
            return _tool_error(f"Invalid argument: {exc}")
        text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str)
        return {"content": [{"type": "text", "text": text}], "isError": False}


def serve_stdio(
    client: TetraClient,
    *,
    allow_writes: bool = False,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> None:
    """Run the newline-delimited JSON-RPC loop until stdin closes."""
    server = MCPServer(client, allow_writes=allow_writes)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue  # MCP stdio: ignore anything that isn't a JSON-RPC message
        response = server.handle_message(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
