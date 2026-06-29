"""Pre-defined Docker app catalog — compose templates used directly (no Coolify in the data path).

Source: the Coolify ``service-templates.json`` catalog (Apache-2.0). Each entry is metadata plus a
base64 ``docker-compose`` file. We fetch + cache it, then **render it ourselves**: Coolify's compose
files reference "magic" ``SERVICE_*`` variables that Coolify generates at deploy time; since we run the
compose directly, we re-implement that generator (random passwords/users/base64 secrets, FQDN/URL) and
return a concrete env map that ``docker compose`` interpolates.
"""

import base64
import binascii
import re
import secrets
import string
from dataclasses import dataclass
from typing import Any

import httpx
import yaml
from pydantic import BaseModel

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import request_json

# jsDelivr CDN mirror of coollabsio/coolify templates/service-templates.json (Apache-2.0).
DEFAULT_CATALOG_URL = (
    "https://cdn.jsdelivr.net/gh/coollabsio/coolify@main/templates/service-templates.json"
)

# SERVICE_<KIND>[_64]_<NAME>[_<PORT>] — Coolify's magic-variable convention.
_SERVICE_TOKEN = re.compile(r"SERVICE_(FQDN|URL|USER|PASSWORD|BASE64|REALBASE64)(_64)?_[A-Z0-9]+(?:_\d+)?")


class AppTemplate(BaseModel):
    slug: str
    name: str
    description: str = ""
    category: str = ""
    tags: list[str] = []
    logo: str = ""
    port: str = ""
    compose_b64: str = ""

    def decoded_compose(self) -> str:
        try:
            return base64.b64decode(self.compose_b64).decode("utf-8", "replace")
        except (binascii.Error, ValueError):
            return ""


def _titleize(slug: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", slug) if part)


def normalize_template(slug: str, raw: dict[str, Any]) -> AppTemplate:
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return AppTemplate(
        slug=slug,
        name=str(raw.get("name") or _titleize(slug)),
        description=str(raw.get("slogan") or raw.get("description") or ""),
        category=str(raw.get("category") or "other"),
        tags=[str(tag) for tag in tags],
        logo=str(raw.get("logo") or ""),
        port=str(raw.get("port") or ""),
        compose_b64=str(raw.get("compose") or ""),
    )


def _rand(alphabet: str, length: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))


def render_service_vars(compose_yaml: str, *, domain: str = "") -> dict[str, str]:
    """Scan a compose file for SERVICE_* tokens and generate a concrete value for each.

    Returns an env map that ``docker compose`` interpolates (``${SERVICE_...}``) or passes through
    (bare ``SERVICE_...`` entries in an ``environment:`` list). Each distinct token gets one value.
    """
    env: dict[str, str] = {}
    # finditer (not findall) so we get the full matched token, since the pattern has groups.
    for match in _SERVICE_TOKEN.finditer(compose_yaml):
        token = match.group(0)
        if token not in env:
            env[token] = _value_for_token(token, domain=domain)
    return env


def _referenced_volume_name(entry: Any) -> str | None:
    """Return the named-volume referenced by a service `volumes:` entry, or None for binds."""
    if isinstance(entry, dict):  # long syntax
        if entry.get("type") == "volume" and entry.get("source"):
            return str(entry["source"])
        return None
    if isinstance(entry, str):  # short syntax "name:/path[:mode]"
        source = entry.split(":", 1)[0].strip()
        if source and not source.startswith(("/", ".", "~", "$")):
            return source
    return None


def normalize_compose_for_engine(compose_yaml: str) -> str:
    """Make a Coolify template runnable by plain `docker compose`.

    Coolify auto-declares named volumes that services reference; plain compose requires
    them in the top-level `volumes:` map or it rejects the project. Declare any missing ones.
    """
    try:
        doc = yaml.safe_load(compose_yaml)
    except yaml.YAMLError:
        return compose_yaml
    if not isinstance(doc, dict):
        return compose_yaml

    services = doc.get("services") or {}
    referenced: set[str] = set()
    for service in services.values():
        if not isinstance(service, dict):
            continue
        for entry in service.get("volumes") or []:
            name = _referenced_volume_name(entry)
            if name:
                referenced.add(name)
    if not referenced:
        return compose_yaml

    declared = doc.get("volumes")
    if not isinstance(declared, dict):
        declared = {}
    for name in referenced:
        declared.setdefault(name, {})
    doc["volumes"] = declared
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def _value_for_token(token: str, *, domain: str) -> str:
    long = "_64_" in token or token.endswith("_64")
    if token.startswith("SERVICE_FQDN_"):
        return domain
    if token.startswith("SERVICE_URL_"):
        return f"https://{domain}" if domain else ""
    if token.startswith("SERVICE_USER_"):
        return _rand(string.ascii_lowercase + string.digits, 12)
    if token.startswith("SERVICE_PASSWORD_"):
        return _rand(string.ascii_letters + string.digits, 64 if long else 24)
    if token.startswith(("SERVICE_BASE64_", "SERVICE_REALBASE64_")):
        return secrets.token_urlsafe(48 if long else 24)
    return _rand(string.ascii_letters + string.digits, 24)


@dataclass(slots=True)
class AppCatalog:
    http_client: httpx.AsyncClient
    cache: TTLCache
    catalog_url: str = DEFAULT_CATALOG_URL

    @classmethod
    def from_request(cls, request: Any) -> "AppCatalog":
        url = getattr(get_settings(), "app_catalog_url", "") or DEFAULT_CATALOG_URL
        return cls(
            http_client=request.app.state.http_client,
            cache=request.app.state.cache,
            catalog_url=url,
        )

    async def list_templates(self, refresh: bool = False) -> list[AppTemplate]:
        cache_key = "catalog:templates"

        async def fetch() -> list[AppTemplate]:
            payload = await request_json(
                self.http_client, service="Catalog", method="GET", url=self.catalog_url
            )
            if not isinstance(payload, dict):
                return []
            templates = [normalize_template(slug, raw) for slug, raw in payload.items() if isinstance(raw, dict)]
            templates.sort(key=lambda template: template.name.lower())
            return templates

        if refresh:
            await self.cache.delete(cache_key)
        # Catalog is large and rarely changes — cache for an hour minimum.
        ttl = max(3600, get_settings().provider_cache_ttl_seconds)
        return await self.cache.get_or_set(cache_key, ttl, fetch)

    async def get_template(self, slug: str) -> AppTemplate | None:
        for template in await self.list_templates():
            if template.slug == slug:
                return template
        return None
