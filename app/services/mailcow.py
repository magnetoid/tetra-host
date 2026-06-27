from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class MailcowDomain:
    id: str
    domain: str
    description: str
    active: str
    aliases: int
    mailboxes: int
    quota: str


@dataclass
class MailcowClient:
    base_url: str
    api_key: str

    @classmethod
    def from_settings(cls) -> "MailcowClient":
        s = get_settings()
        return cls(base_url=s.mailcow_url.rstrip("/"), api_key=s.mailcow_api_key)

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_domains(self) -> list[MailcowDomain]:
        if not self.is_configured():
            return self.placeholder_domains()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(f"{self.base_url}/api/v1/get/domain/all", headers=self.headers())
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return self.placeholder_domains()

        items = self._extract_items(payload)
        if not items:
            return self.placeholder_domains()
        return [self.normalize_domain(item) for item in items]

    def _extract_items(self, payload: object) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("data", "items", "domains"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            if "domain_name" in payload or "domain" in payload:
                return [payload]
        return []

    def normalize_domain(self, raw: dict) -> MailcowDomain:
        return MailcowDomain(
            id=str(raw.get("id") or raw.get("domain_name") or raw.get("domain") or "unknown"),
            domain=str(raw.get("domain_name") or raw.get("domain") or "Unknown domain"),
            description=str(raw.get("description") or raw.get("defquota") or "Mail domain"),
            active="Yes" if str(raw.get("active", "1")) in {"1", "true", "True"} else "No",
            aliases=int(raw.get("aliases_in_domain") or raw.get("max_num_aliases_for_domain") or 0),
            mailboxes=int(raw.get("mboxes_in_domain") or raw.get("max_num_mboxes_for_domain") or 0),
            quota=str(raw.get("maxquota_for_domain") or raw.get("quota_used_in_domain") or "—"),
        )

    def placeholder_domains(self) -> list[MailcowDomain]:
        return [
            MailcowDomain("imbaproduction.com", "imbaproduction.com", "Mail domain", "Planned", 0, 0, "—"),
            MailcowDomain("imbamarketing.com", "imbamarketing.com", "Mail domain", "Planned", 0, 0, "—"),
        ]
