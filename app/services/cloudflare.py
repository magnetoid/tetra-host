import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json, request_text

# GraphQL Analytics endpoint (the REST zone-analytics API is deprecated).
CLOUDFLARE_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

# Daily HTTP analytics for a zone — broadly available (incl. free plans).
_ZONE_ANALYTICS_QUERY = """
query ZoneDailyAnalytics($zoneTag: String!, $since: String!, $until: String!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      httpRequests1dGroups(
        limit: 60
        filter: { date_geq: $since, date_leq: $until }
        orderBy: [date_ASC]
      ) {
        dimensions { date }
        sum { requests bytes cachedRequests cachedBytes threats }
        uniq { uniques }
      }
    }
  }
}
"""


class CloudflareZone(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    status: str
    account_name: str = ""
    paused: bool = False


class CloudflareDNSRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    type: str
    name: str
    content: str
    ttl: int
    proxied: bool | None = None
    priority: int | None = None


def normalize_zone(raw: dict[str, Any]) -> CloudflareZone:
    return CloudflareZone(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or "unknown"),
        status=str(raw.get("status") or "unknown"),
        account_name=str((raw.get("account") or {}).get("name") or ""),
        paused=bool(raw.get("paused", False)),
    )


def normalize_record(raw: dict[str, Any]) -> CloudflareDNSRecord:
    priority = raw.get("priority")
    if priority is None and isinstance(raw.get("data"), dict):
        priority = raw["data"].get("priority")
    return CloudflareDNSRecord(
        id=str(raw.get("id") or ""),
        type=str(raw.get("type") or ""),
        name=str(raw.get("name") or ""),
        content=str(raw.get("content") or ""),
        ttl=int(raw.get("ttl") or 0),
        proxied=raw.get("proxied"),
        priority=int(priority) if priority is not None else None,
    )


def normalize_analytics(payload: Any, *, since: str, until: str) -> dict[str, Any]:
    """Flatten the GraphQL httpRequests1dGroups response into points + totals."""
    points: list[dict[str, Any]] = []
    try:
        groups = payload["data"]["viewer"]["zones"][0]["httpRequests1dGroups"]
    except (KeyError, IndexError, TypeError):
        groups = []

    totals = {"requests": 0, "bytes": 0, "cached_requests": 0, "threats": 0, "uniques": 0}
    for group in groups or []:
        summed = group.get("sum") or {}
        uniq = group.get("uniq") or {}
        point = {
            "date": str((group.get("dimensions") or {}).get("date") or ""),
            "requests": int(summed.get("requests") or 0),
            "bytes": int(summed.get("bytes") or 0),
            "cached_requests": int(summed.get("cachedRequests") or 0),
            "threats": int(summed.get("threats") or 0),
            "uniques": int(uniq.get("uniques") or 0),
        }
        points.append(point)
        totals["requests"] += point["requests"]
        totals["bytes"] += point["bytes"]
        totals["cached_requests"] += point["cached_requests"]
        totals["threats"] += point["threats"]
        totals["uniques"] += point["uniques"]

    return {"since": since, "until": until, "points": points, "totals": totals}


def count_bind_records(bind_text: str) -> int:
    """Count actual records in a BIND zone file (skip blanks/comments/directives)."""
    count = 0
    for line in (bind_text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("$"):
            continue
        count += 1
    return count


class CloudflareClient:
    def __init__(
        self,
        *,
        api_token: str,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.api_token = api_token
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(
        cls,
        *,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> "CloudflareClient":
        return cls(
            api_token=get_settings().cloudflare_api_token,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.api_token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Accept": "application/json"}

    async def list_zones(self, refresh: bool = False) -> list[CloudflareZone]:
        if not self.is_configured():
            return []

        settings = get_settings()

        async def fetch() -> list[CloudflareZone]:
            payload = await request_json(
                self.http_client,
                service="Cloudflare",
                method="GET",
                url="https://api.cloudflare.com/client/v4/zones",
                headers=self.headers(),
                params={"per_page": 50},
            )
            return [normalize_zone(item) for item in payload.get("result", [])]

        if refresh:
            await self.cache.delete("cloudflare:zones")
        return await self.cache.get_or_set(
            "cloudflare:zones",
            settings.provider_cache_ttl_seconds,
            fetch,
        )

    async def list_dns_records(self, zone_id: str, refresh: bool = False) -> list[CloudflareDNSRecord]:
        if not self.is_configured() or not zone_id:
            return []

        settings = get_settings()
        cache_key = f"cloudflare:records:{zone_id}"

        async def fetch() -> list[CloudflareDNSRecord]:
            payload = await request_json(
                self.http_client,
                service="Cloudflare",
                method="GET",
                url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                headers=self.headers(),
                params={"per_page": 100},
            )
            return [normalize_record(item) for item in payload.get("result", [])]

        if refresh:
            await self.cache.delete(cache_key)
        return await self.cache.get_or_set(cache_key, settings.provider_cache_ttl_seconds, fetch)

    async def create_dns_record(
        self, zone_id: str, record_type: str, name: str, content: str,
        ttl: int = 1, proxied: bool = False, priority: int | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        body: dict[str, Any] = {"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied}
        if priority is not None:
            body["priority"] = priority
        payload = await request_json(
            self.http_client, service="Cloudflare", method="POST",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
            headers=self.headers(), json_body=body,
        )
        await self.cache.delete(f"cloudflare:records:{zone_id}")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def update_dns_record(
        self, zone_id: str, record_id: str, record_type: str, name: str,
        content: str, ttl: int = 1, proxied: bool = False, priority: int | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        body: dict[str, Any] = {"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied}
        if priority is not None:
            body["priority"] = priority
        payload = await request_json(
            self.http_client, service="Cloudflare", method="PUT",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
            headers=self.headers(), json_body=body,
        )
        await self.cache.delete(f"cloudflare:records:{zone_id}")
        return payload if isinstance(payload, dict) else {"ok": True}

    async def delete_dns_record(self, zone_id: str, record_id: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        payload = await request_json(
            self.http_client, service="Cloudflare", method="DELETE",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
            headers=self.headers(),
        )
        await self.cache.delete(f"cloudflare:records:{zone_id}")
        return payload if isinstance(payload, dict) else {"ok": True}

    # ── Zone settings / tools ─────────────────────────────────────

    ZONE_SETTING_KEYS = ("ssl", "always_use_https", "development_mode", "security_level")

    async def get_zone_setting(self, zone_id: str, setting: str) -> Any:
        if not self.is_configured():
            return None
        payload = await request_json(
            self.http_client, service="Cloudflare", method="GET",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/settings/{setting}",
            headers=self.headers(),
        )
        return (payload.get("result") or {}).get("value") if isinstance(payload, dict) else None

    async def get_zone_settings(self, zone_id: str) -> dict[str, str]:
        """Fetch the panel-managed zone settings + DNSSEC status in one shot."""
        if not self.is_configured():
            return {}

        async def one(key: str) -> tuple[str, str]:
            try:
                value = await self.get_zone_setting(zone_id, key)
            except ProviderAPIError:
                value = None
            return key, "" if value is None else str(value)

        settings = dict(await asyncio.gather(*(one(key) for key in self.ZONE_SETTING_KEYS)))
        try:
            dnssec = await request_json(
                self.http_client, service="Cloudflare", method="GET",
                url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dnssec",
                headers=self.headers(),
            )
            settings["dnssec"] = str((dnssec.get("result") or {}).get("status") or "") if isinstance(dnssec, dict) else ""
        except ProviderAPIError:
            settings["dnssec"] = ""
        return settings

    async def update_zone_setting(self, zone_id: str, setting: str, value: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        payload = await request_json(
            self.http_client, service="Cloudflare", method="PATCH",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/settings/{setting}",
            headers=self.headers(), json_body={"value": value},
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def update_dnssec(self, zone_id: str, status: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        payload = await request_json(
            self.http_client, service="Cloudflare", method="PATCH",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dnssec",
            headers=self.headers(), json_body={"status": status},
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    async def purge_cache(self, zone_id: str, *, everything: bool = True, files: list[str] | None = None) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        body: dict[str, Any] = {"purge_everything": True} if everything or not files else {"files": files}
        payload = await request_json(
            self.http_client, service="Cloudflare", method="POST",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache",
            headers=self.headers(), json_body=body,
        )
        return payload if isinstance(payload, dict) else {"ok": True}

    # ── Analytics (GraphQL) ───────────────────────────────────────

    async def get_zone_analytics(self, zone_id: str, *, days: int = 7) -> dict[str, Any]:
        """Daily HTTP analytics for a zone over the trailing ``days`` window."""
        if not self.is_configured():
            return {"since": "", "until": "", "points": [], "totals": {}}

        days = max(1, min(days, 60))
        until = datetime.now(timezone.utc).date()
        since = until - timedelta(days=days - 1)
        payload = await request_json(
            self.http_client, service="Cloudflare", method="POST",
            url=CLOUDFLARE_GRAPHQL_URL, headers=self.headers(),
            json_body={
                "query": _ZONE_ANALYTICS_QUERY,
                "variables": {
                    "zoneTag": zone_id,
                    "since": since.isoformat(),
                    "until": until.isoformat(),
                },
            },
        )
        # GraphQL returns HTTP 200 even on query errors — surface them explicitly.
        if isinstance(payload, dict) and payload.get("errors"):
            messages = "; ".join(str(e.get("message", e)) for e in payload["errors"])
            raise ProviderAPIError(service="Cloudflare", message=f"Analytics query failed: {messages}")
        return normalize_analytics(payload, since=since.isoformat(), until=until.isoformat())

    # ── Bulk import / export (BIND) ───────────────────────────────

    async def export_dns_records(self, zone_id: str) -> str:
        """Return the zone's records as a BIND-format zone file (text)."""
        if not self.is_configured():
            return ""
        return await request_text(
            self.http_client, service="Cloudflare", method="GET",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/export",
            headers=self.headers(),
        )

    async def import_dns_records(self, zone_id: str, bind_text: str) -> dict[str, Any]:
        """Import a BIND-format zone file via the multipart import endpoint."""
        if not self.is_configured():
            return {"ok": False, "message": "Cloudflare is not configured."}
        payload = await request_json(
            self.http_client, service="Cloudflare", method="POST",
            url=f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/import",
            headers=self.headers(),
            files={"file": ("import.txt", bind_text.encode("utf-8"), "text/plain")},
        )
        await self.cache.delete(f"cloudflare:records:{zone_id}")
        return payload if isinstance(payload, dict) else {"ok": True}
