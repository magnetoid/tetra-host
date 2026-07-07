"""Hetzner Cloud client — own-infrastructure provisioning (ADR 0004 Phase 3).

Direct hcloud REST calls for hot-path single actions (create/list/delete server), per
the platform research: reference platforms don't run IaC in the request path. Mutations
return async **Action** objects that must be polled to completion. Rate limit is 3,600
requests/hour per token — all calls go through the shared retrying ``request_json``
helper so 429s back off centrally. Shapes verified against the official OpenAPI spec
(docs.hetzner.cloud/cloud.spec.json, 2026-07-02).
"""

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json

HETZNER_API = "https://api.hetzner.cloud/v1"

# First-boot bootstrap: Docker via get.docker.com. cloud-init is fire-and-forget — a
# failed runcmd does NOT fail the create call; callers must poll/SSH to confirm.
DEFAULT_CLOUD_INIT = """#cloud-config
package_update: true
runcmd:
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable --now docker
"""


def mailcow_cloud_init(hostname: str, *, tz: str = "Etc/UTC") -> str:
    """cloud-init for a DEDICATED Mailcow host: Docker + mailcow-dockerized brought up
    on the standard mail ports (25/465/587/143/993/995) and 80/443.

    This is the automated form of ``scripts/install-mailcow.sh`` (the canonical manual
    installer). A fresh Hetzner box owns every port, so that script's shared-box port
    guards are unnecessary here. Like ``DEFAULT_CLOUD_INIT`` it is fire-and-forget: the
    create Action returns once the VM exists, but the ~15-minute image pull continues
    after boot — poll/SSH to confirm, then create an API key in the Mailcow UI and set
    ``MAILCOW_URL`` / ``MAILCOW_API_KEY`` to activate the (already shipped) mail surface.

    ``hostname``/``tz`` are operator-supplied config (validated at the route), embedded
    into a heredoc'd install script so a value can't break out of a runcmd string.
    """
    return f"""#cloud-config
package_update: true
packages:
  - git
  - curl
write_files:
  - path: /opt/tetra-install-mailcow.sh
    permissions: '0755'
    content: |
      #!/usr/bin/env bash
      set -euo pipefail
      curl -fsSL https://get.docker.com | sh
      systemctl enable --now docker
      git clone https://github.com/mailcow/mailcow-dockerized /opt/mailcow-dockerized
      cd /opt/mailcow-dockerized
      MAILCOW_HOSTNAME={hostname} MAILCOW_TZ={tz} ./generate_config.sh
      docker compose pull
      docker compose up -d
runcmd:
  - [ bash, /opt/tetra-install-mailcow.sh ]
"""


class HetznerServer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    name: str
    status: str = ""
    server_type: str = ""
    ipv4: str = ""
    location: str = ""
    created: str = ""


def normalize_server(item: dict[str, Any]) -> HetznerServer:
    public_net = item.get("public_net") or {}
    ipv4 = (public_net.get("ipv4") or {}).get("ip") or ""
    server_type = (item.get("server_type") or {}).get("name") or ""
    datacenter = item.get("datacenter") or {}
    location = ((datacenter.get("location") or {}).get("name")) or ""
    return HetznerServer(
        id=int(item.get("id") or 0),
        name=str(item.get("name") or ""),
        status=str(item.get("status") or ""),
        server_type=server_type,
        ipv4=ipv4,
        location=location,
        created=str(item.get("created") or ""),
    )


class HetznerClient:
    def __init__(
        self, *, api_token: str, http_client: httpx.AsyncClient, cache: TTLCache
    ) -> None:
        self.api_token = api_token
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(
        cls, *, http_client: httpx.AsyncClient, cache: TTLCache
    ) -> "HetznerClient":
        return cls(
            api_token=get_settings().hetzner_api_token,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.api_token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Accept": "application/json"}

    async def list_servers(self, refresh: bool = False) -> list[HetznerServer]:
        if not self.is_configured():
            return []

        async def fetch() -> list[HetznerServer]:
            payload = await request_json(
                self.http_client, service="Hetzner", method="GET",
                url=f"{HETZNER_API}/servers", headers=self.headers(), params={"per_page": 50},
            )
            return [normalize_server(item) for item in payload.get("servers", [])]

        if refresh:
            await self.cache.delete("hetzner:servers")
        return await self.cache.get_or_set(
            "hetzner:servers", get_settings().provider_cache_ttl_seconds, fetch
        )

    async def get_server(self, server_id: int) -> HetznerServer | None:
        payload = await request_json(
            self.http_client, service="Hetzner", method="GET",
            url=f"{HETZNER_API}/servers/{server_id}", headers=self.headers(),
        )
        item = payload.get("server")
        return normalize_server(item) if isinstance(item, dict) else None

    async def create_server(
        self,
        *,
        name: str,
        server_type: str,
        image: str,
        location: str = "",
        user_data: str = "",
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """POST /servers — returns {server, action, root_password} (password only when
        no SSH key is attached; surface it once, never store it)."""
        body: dict[str, Any] = {"name": name, "server_type": server_type, "image": image}
        if location:
            body["location"] = location
        if user_data:
            body["user_data"] = user_data
        if labels:
            body["labels"] = labels
        payload = await request_json(
            self.http_client, service="Hetzner", method="POST",
            url=f"{HETZNER_API}/servers", headers=self.headers(), json_body=body,
        )
        await self.cache.delete("hetzner:servers")
        return payload if isinstance(payload, dict) else {}

    async def delete_server(self, server_id: int) -> dict[str, Any]:
        payload = await request_json(
            self.http_client, service="Hetzner", method="DELETE",
            url=f"{HETZNER_API}/servers/{server_id}", headers=self.headers(),
        )
        await self.cache.delete("hetzner:servers")
        return payload if isinstance(payload, dict) else {}

    async def get_action(self, action_id: int) -> dict[str, Any]:
        payload = await request_json(
            self.http_client, service="Hetzner", method="GET",
            url=f"{HETZNER_API}/actions/{action_id}", headers=self.headers(),
        )
        return payload.get("action", {}) if isinstance(payload, dict) else {}

    async def wait_action(
        self, action_id: int, *, poll_interval: float = 2.0, max_seconds: float = 180.0
    ) -> str:
        """Poll an Action to a terminal state; returns 'success' | 'error' | 'running'
        (the latter on timeout). Never raises on action failure — callers decide."""
        elapsed = 0.0
        while elapsed < max_seconds:
            action = await self.get_action(action_id)
            status = str(action.get("status") or "")
            if status in {"success", "error"}:
                return status
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        return "running"


__all__ = [
    "DEFAULT_CLOUD_INIT",
    "HetznerClient",
    "HetznerServer",
    "ProviderAPIError",
    "mailcow_cloud_init",
    "normalize_server",
]
