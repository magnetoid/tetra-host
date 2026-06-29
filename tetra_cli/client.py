"""Thin httpx client over the Tetra Host /api/v1 contract.

A ``transport`` can be injected (e.g. ``httpx.ASGITransport(app=...)``) so the
CLI can be tested in-process against the FastAPI app without a live server.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx


class TetraError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class TetraClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        self.token = token
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self._transport, timeout=self._timeout)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, *, json_body: Any = None, params: dict | None = None) -> Any:
        with self._client() as client:
            response = client.request(
                method, f"{self.api}{path}", headers=self._headers(), json=json_body, params=params
            )
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            detail: Any = response.text
            try:
                detail = response.json().get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise TetraError(str(detail), response.status_code)
        try:
            return response.json()
        except ValueError:
            return response.text

    # ── Auth ──────────────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> str:
        data = self._request("POST", "/auth/login", json_body={"email": email, "password": password})
        self.token = data["token"]
        return self.token

    def me(self) -> Any:
        return self._request("GET", "/auth/me")

    def dashboard(self) -> Any:
        return self._request("GET", "/dashboard")

    # ── Sites / deploys ───────────────────────────────────────────────────
    def sites(self) -> list[dict]:
        return self._request("GET", "/sites")

    def deploy(self, site_id: str, force: bool = False) -> Any:
        return self._request("POST", f"/sites/{site_id}/deploy", params={"force": "1"} if force else None)

    def deployments(self, site_id: str) -> list[dict]:
        return self._request("GET", f"/sites/{site_id}/deployments")

    def stream_logs(self, site_id: str, deployment_id: str) -> Iterator[tuple[str, dict]]:
        """Yield (event, data) tuples from the SSE build-log stream until done."""
        url = f"{self.api}/sites/{site_id}/deployments/{deployment_id}/logs/stream"
        with self._client() as client, client.stream("GET", url, headers=self._headers()) as response:
            if response.status_code >= 400:
                raise TetraError(f"log stream failed ({response.status_code})", response.status_code)
            event = "message"
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        data = json.loads(payload)
                    except ValueError:
                        data = {"raw": payload}
                    yield event, data
                    event = "message"

    # ── DNS ───────────────────────────────────────────────────────────────
    def dns(self, zone: str | None = None) -> Any:
        return self._request("GET", "/dns", params={"zone": zone} if zone else None)

    def dns_add(
        self, zone_id: str, record_type: str, name: str, content: str, ttl: int = 1, proxied: bool = False
    ) -> Any:
        return self._request(
            "POST",
            f"/dns/zones/{zone_id}/records",
            json_body={"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied},
        )

    def dns_update(
        self,
        zone_id: str,
        record_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        priority: int | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied,
        }
        if priority is not None:
            body["priority"] = priority
        return self._request("PUT", f"/dns/zones/{zone_id}/records/{record_id}", json_body=body)

    def dns_rm(self, zone_id: str, record_id: str) -> Any:
        return self._request("DELETE", f"/dns/zones/{zone_id}/records/{record_id}")

    # ── Zone tools ────────────────────────────────────────────────────────
    def zone_settings(self, zone_id: str) -> Any:
        return self._request("GET", f"/dns/zones/{zone_id}/settings")

    def zone_set(self, zone_id: str, setting: str, value: str) -> Any:
        return self._request(
            "PATCH", f"/dns/zones/{zone_id}/settings", json_body={"setting": setting, "value": value}
        )

    def zone_dnssec(self, zone_id: str, status: str) -> Any:
        return self._request("PATCH", f"/dns/zones/{zone_id}/dnssec", json_body={"status": status})

    def zone_purge(self, zone_id: str, everything: bool = True, files: list[str] | None = None) -> Any:
        return self._request(
            "POST", f"/dns/zones/{zone_id}/purge", json_body={"everything": everything, "files": files or []}
        )

    def zone_analytics(self, zone_id: str, days: int = 7) -> Any:
        return self._request("GET", f"/dns/zones/{zone_id}/analytics", params={"days": days})

    def dns_export(self, zone_id: str) -> Any:
        return self._request("GET", f"/dns/zones/{zone_id}/export")

    def dns_import(self, zone_id: str, bind: str) -> Any:
        return self._request("POST", f"/dns/zones/{zone_id}/import", json_body={"bind": bind})

    # ── Env vars ──────────────────────────────────────────────────────────
    def envs(self, site_id: str) -> list[dict]:
        return self._request("GET", f"/sites/{site_id}/envs")

    def env_set(self, site_id: str, key: str, value: str) -> Any:
        return self._request("POST", f"/sites/{site_id}/envs", json_body={"key": key, "value": value})

    def env_rm(self, site_id: str, env_uuid: str) -> Any:
        return self._request("DELETE", f"/sites/{site_id}/envs/{env_uuid}")

    # ── Apps (Tetra Engine — pre-defined Docker containers) ───────────────
    def apps_catalog(self, search: str | None = None, category: str | None = None) -> Any:
        params: dict[str, str] = {}
        if search:
            params["search"] = search
        if category:
            params["category"] = category
        return self._request("GET", "/apps/catalog", params=params or None)

    def apps(self) -> Any:
        return self._request("GET", "/apps")

    def apps_install(self, slug: str, name: str | None = None, domain: str | None = None) -> Any:
        body: dict[str, str] = {"slug": slug}
        if name:
            body["name"] = name
        if domain:
            body["domain"] = domain
        return self._request("POST", "/apps/install", json_body=body)

    def apps_start(self, project: str) -> Any:
        return self._request("POST", f"/apps/{project}/start")

    def apps_stop(self, project: str) -> Any:
        return self._request("POST", f"/apps/{project}/stop")

    def apps_rm(self, project: str, volumes: bool = False) -> Any:
        return self._request("DELETE", f"/apps/{project}", params={"volumes": "1"} if volumes else None)

    def apps_logs(self, project: str) -> Any:
        return self._request("GET", f"/apps/{project}/logs")

    # ── Deploys (build & run git repos) ───────────────────────────────────
    def deploy_git(self, git_url: str, name: str, ref: str = "main", port: int = 3000) -> Any:
        return self._request(
            "POST", "/deploys/git",
            json_body={"git_url": git_url, "ref": ref, "name": name, "port": port},
        )
