from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json

# Write-op envelope: mailcow answers HTTP 200 with [{type: success|danger|error, msg, log}]
# (occasionally a bare object) — a 200 "danger"/"error" is a FAILED operation.
_FAILURE_TYPES = {"danger", "error"}

# Dedicated, TLS-non-verifying client for a self-signed Mailcow endpoint (e.g. the
# co-located loopback instance). Cached at module scope so we don't leak a client
# per request; only built when mailcow_verify_tls is false.
_insecure_client: httpx.AsyncClient | None = None


def _insecure_http_client() -> httpx.AsyncClient:
    global _insecure_client
    if _insecure_client is None:
        _insecure_client = httpx.AsyncClient(verify=False, timeout=httpx.Timeout(30.0))
    return _insecure_client

_CACHE_KEYS = ("mailcow:domains", "mailcow:mailboxes", "mailcow:aliases")


def _failure_message(payload: Any) -> str | None:
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        if isinstance(item, dict) and item.get("type") in _FAILURE_TYPES:
            msg = item.get("msg")
            text = " ".join(str(part) for part in msg) if isinstance(msg, list) else str(msg or "")
            return text or "Mailcow rejected the operation."
    return None


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


class MailcowAlias(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    address: str
    goto: str = ""
    domain: str = ""
    active: bool = True


def normalize_alias(raw: dict[str, Any]) -> MailcowAlias:
    address = str(raw.get("address") or "")
    return MailcowAlias(
        id=int(raw.get("id") or 0),
        address=address,
        goto=str(raw.get("goto") or ""),
        domain=address.split("@", 1)[-1] if "@" in address else str(raw.get("domain") or ""),
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
        client = http_client if s.mailcow_verify_tls else _insecure_http_client()
        return cls(
            base_url=s.mailcow_url,
            api_key=s.mailcow_api_key,
            http_client=client,
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

    async def list_aliases(self, refresh: bool = False) -> list[MailcowAlias]:
        if not self.is_configured():
            return []

        settings = get_settings()

        async def fetch() -> list[MailcowAlias]:
            payload = await request_json(
                self.http_client,
                service="Mailcow",
                method="GET",
                url=f"{self.base_url}/api/v1/get/alias/all",
                headers=self.headers(),
            )
            return [normalize_alias(item) for item in payload]

        if refresh:
            await self.cache.delete("mailcow:aliases")
        return await self.cache.get_or_set(
            "mailcow:aliases", settings.provider_cache_ttl_seconds, fetch
        )

    # ── Write operations (Phase 2) ──────────────────────────────────────────
    # Shapes verified against mailcow's shipped openapi.yaml — see
    # docs/providers/combined-api-reference.md. Unlike reads (which degrade to
    # empty lists), writes on an unconfigured client are an error.

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise ProviderAPIError(
                service="Mailcow", message="Mailcow is not configured.", status_code=503
            )

    async def _write(self, path: str, body: Any) -> Any:
        self._require_configured()
        payload = await request_json(
            self.http_client,
            service="Mailcow",
            method="POST",
            url=f"{self.base_url}/api/v1/{path}",
            headers=self.headers(),
            json_body=body,
        )
        failure = _failure_message(payload)
        if failure:
            raise ProviderAPIError(service="Mailcow", message=failure, status_code=422)
        for key in _CACHE_KEYS:
            await self.cache.delete(key)
        return payload

    async def create_domain(
        self,
        domain: str,
        *,
        description: str = "",
        quota_mb: int = 10240,
        max_quota_mb: int = 10240,
        def_quota_mb: int = 3072,
        max_mailboxes: int = 10,
        max_aliases: int = 400,
    ) -> Any:
        return await self._write(
            "add/domain",
            {
                "domain": domain,
                "description": description,
                "active": "1",
                "quota": str(quota_mb),
                "maxquota": str(max_quota_mb),
                "defquota": str(def_quota_mb),
                "mailboxes": str(max_mailboxes),
                "aliases": str(max_aliases),
                "restart_sogo": "1",
            },
        )

    async def delete_domain(self, domain: str) -> Any:
        return await self._write("delete/domain", [domain])

    async def create_mailbox(
        self,
        local_part: str,
        domain: str,
        *,
        password: str,
        name: str = "",
        quota_mb: int = 3072,
        force_pw_update: bool = False,
    ) -> Any:
        return await self._write(
            "add/mailbox",
            {
                "local_part": local_part,
                "domain": domain,
                "name": name,
                "password": password,
                "password2": password,
                "quota": str(quota_mb),
                "active": "1",
                "force_pw_update": "1" if force_pw_update else "0",
            },
        )

    async def delete_mailbox(self, username: str) -> Any:
        return await self._write("delete/mailbox", [username])

    async def create_alias(self, address: str, goto: str) -> Any:
        return await self._write("add/alias", {"address": address, "goto": goto, "active": "1"})

    async def delete_alias(self, alias_id: int | str) -> Any:
        return await self._write("delete/alias", [str(alias_id)])

    async def get_dkim(self, domain: str) -> dict[str, Any]:
        self._require_configured()
        payload = await request_json(
            self.http_client,
            service="Mailcow",
            method="GET",
            url=f"{self.base_url}/api/v1/get/dkim/{domain}",
            headers=self.headers(),
        )
        return payload if isinstance(payload, dict) else {}

    async def generate_dkim(
        self, domain: str, *, selector: str = "dkim", key_size: int = 2048
    ) -> Any:
        return await self._write(
            "add/dkim",
            {"domains": domain, "dkim_selector": selector, "key_size": str(key_size)},
        )

    async def create_relayhost(self, hostname: str, username: str, password: str) -> Any:
        return await self._write(
            "add/relayhost",
            {"hostname": hostname, "username": username, "password": password},
        )

    async def list_relayhosts(self) -> list[dict[str, Any]]:
        self._require_configured()
        payload = await request_json(
            self.http_client,
            service="Mailcow",
            method="GET",
            url=f"{self.base_url}/api/v1/get/relayhost/all",
            headers=self.headers(),
        )
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    async def assign_relayhost(self, domain: str, relayhost_id: int | str) -> Any:
        return await self._write(
            "edit/domain",
            {"items": [domain], "attr": {"relayhost": str(relayhost_id)}},
        )