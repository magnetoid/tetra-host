from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json


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
