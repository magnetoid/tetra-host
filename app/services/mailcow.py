from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json


class MailcowDomain(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    domain_name: str
    mailboxes: int = 0
    aliases: int = 0
    quota_bytes: int = 0
    active: bool = True


class MailcowMailbox(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str
    name: str = ""
    domain: str
    quota_bytes: int = 0
    messages: int = 0
    active: bool = True


def normalize_domain(raw: dict[str, Any]) -> MailcowDomain:
    return MailcowDomain(
        domain_name=str(raw.get("domain_name") or raw.get("domain") or "unknown"),
        mailboxes=int(raw.get("max_num_mboxes_for_domain") or raw.get("mboxes_in_domain") or 0),
        aliases=int(raw.get("max_num_aliases_for_domain") or raw.get("aliases_in_domain") or 0),
        quota_bytes=int(raw.get("maxquota") or raw.get("defquota") or 0),
        active=str(raw.get("active", "1")) in {"1", "true", "True"},
    )


def normalize_mailbox(raw: dict[str, Any]) -> MailcowMailbox:
    username = str(raw.get("username") or raw.get("name") or "")
    domain = username.split("@", 1)[-1] if "@" in username else str(raw.get("domain") or "unknown")
    return MailcowMailbox(
        username=username,
        name=str(raw.get("name") or raw.get("full_name") or ""),
        domain=domain,
        quota_bytes=int(raw.get("quota") or raw.get("quota_bytes") or 0),
        messages=int(raw.get("messages") or 0),
        active=str(raw.get("active", "1")) in {"1", "true", "True"},
    )


class MailcowClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(
        cls,
        *,
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> "MailcowClient":
        s = get_settings()
        return cls(
            base_url=s.mailcow_url,
            api_key=s.mailcow_api_key,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_domains(self, refresh: bool = False) -> list[MailcowDomain]:
        if not self.is_configured():
            return []

        settings = get_settings()

        async def fetch() -> list[MailcowDomain]:
            payload = await request_json(
                self.http_client,
                service="Mailcow",
                method="GET",
                url=f"{self.base_url}/api/v1/get/domain/all",
                headers=self.headers(),
            )
            return [normalize_domain(item) for item in payload]

        if refresh:
            await self.cache.delete("mailcow:domains")
        return await self.cache.get_or_set("mailcow:domains", settings.provider_cache_ttl_seconds, fetch)

    async def list_mailboxes(self, refresh: bool = False) -> list[MailcowMailbox]:
        if not self.is_configured():
            return []

        settings = get_settings()

        async def fetch() -> list[MailcowMailbox]:
            payload = await request_json(
                self.http_client,
                service="Mailcow",
                method="GET",
                url=f"{self.base_url}/api/v1/get/mailbox/all",
                headers=self.headers(),
            )
            return [normalize_mailbox(item) for item in payload]

        if refresh:
            await self.cache.delete("mailcow:mailboxes")
        return await self.cache.get_or_set(
            "mailcow:mailboxes",
            settings.provider_cache_ttl_seconds,
            fetch,
        )