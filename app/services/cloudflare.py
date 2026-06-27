from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class CloudflareZone:
    id: str
    name: str
    status: str
    plan: str
    nameservers: str


@dataclass(frozen=True)
class CloudflareRecord:
    id: str
    zone_id: str
    name: str
    type: str
    content: str
    proxied: str
    ttl: str


@dataclass
class CloudflareClient:
    api_token: str

    @classmethod
    def from_settings(cls) -> "CloudflareClient":
        return cls(api_token=get_settings().cloudflare_api_token)

    def is_configured(self) -> bool:
        return bool(self.api_token)

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_zones(self) -> list[CloudflareZone]:
        if not self.is_configured():
            return self.placeholder_zones()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get("https://api.cloudflare.com/client/v4/zones", headers=self.headers())
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return self.placeholder_zones()

        items = self._extract_items(payload)
        if not items:
            return self.placeholder_zones()
        return [self.normalize_zone(item) for item in items]

    async def list_records(self, zone_id: str) -> list[CloudflareRecord]:
        if not self.is_configured():
            return self.placeholder_records(zone_id)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                    headers=self.headers(),
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return self.placeholder_records(zone_id)

        items = self._extract_items(payload)
        if not items:
            return self.placeholder_records(zone_id)
        return [self.normalize_record(zone_id, item) for item in items]

    def _extract_items(self, payload: object) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            result = payload.get("result")
            if isinstance(result, list):
                return [item for item in result if isinstance(item, dict)]
            if isinstance(result, dict):
                return [result]
        return []

    def normalize_zone(self, raw: dict) -> CloudflareZone:
        plan = raw.get("plan") or {}
        plan_name = plan.get("name") if isinstance(plan, dict) else str(plan or "")
        nameservers = raw.get("name_servers") or raw.get("vanity_name_servers") or []
        if isinstance(nameservers, list):
            ns = ", ".join(nameservers[:2]) if nameservers else "—"
        else:
            ns = str(nameservers)
        return CloudflareZone(
            id=str(raw.get("id") or raw.get("name") or "unknown"),
            name=str(raw.get("name") or "Unknown zone"),
            status=str(raw.get("status") or "unknown"),
            plan=str(plan_name or "—"),
            nameservers=ns,
        )

    def normalize_record(self, zone_id: str, raw: dict) -> CloudflareRecord:
        proxied = raw.get("proxied")
        return CloudflareRecord(
            id=str(raw.get("id") or raw.get("name") or "unknown"),
            zone_id=zone_id,
            name=str(raw.get("name") or "Unknown"),
            type=str(raw.get("type") or "A"),
            content=str(raw.get("content") or "—"),
            proxied="Yes" if proxied is True else "No",
            ttl=str(raw.get("ttl") or "auto"),
        )

    def placeholder_zones(self) -> list[CloudflareZone]:
        return [
            CloudflareZone("montenegro-experience.me", "montenegro-experience.me", "active", "Free", "—"),
            CloudflareZone("imbaproduction.com", "imbaproduction.com", "active", "Free", "—"),
        ]

    def placeholder_records(self, zone_id: str) -> list[CloudflareRecord]:
        return [
            CloudflareRecord(f"{zone_id}-root", zone_id, "@", "A", "65.21.238.89", "No", "auto"),
            CloudflareRecord(f"{zone_id}-www", zone_id, "www", "CNAME", "@", "Yes", "auto"),
            CloudflareRecord(f"{zone_id}-mail", zone_id, "mail", "A", "65.21.238.89", "No", "auto"),
        ]
