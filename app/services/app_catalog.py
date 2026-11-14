"""One-click app catalog — compose templates that ship with the panel.

The catalog lives in the repo (``app/catalog/templates.json``; provenance in
``app/catalog/NOTICE.md``) and is read from disk: nothing is fetched at runtime. Each
entry is metadata plus a base64 ``docker-compose`` file whose ``SERVICE_*`` placeholders
(random users/passwords/secrets, the app's FQDN/URL) are filled in here at install time,
giving a concrete env map that ``docker compose`` interpolates.
"""

import base64
import binascii
import json
import re
import secrets
import string
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "templates.json"

# SERVICE_<KIND>[_64]_<NAME>[_<PORT>] — the catalog's placeholder convention.
_SERVICE_TOKEN = re.compile(r"SERVICE_(FQDN|URL|USER|PASSWORD|BASE64|REALBASE64)(_64)?_[A-Z0-9]+(?:_\d+)?")


class AppTemplate(BaseModel):
    slug: str
    name: str
    description: str = ""
    category: str = ""
    tags: list[str] = []
    # A file name under the console's /catalog/logos/, or "".
    logo: str = ""
    port: str = ""
    documentation: str = ""
    compose_b64: str = ""

    def decoded_compose(self) -> str:
        try:
            return base64.b64decode(self.compose_b64).decode("utf-8", "replace")
        except (binascii.Error, ValueError):
            return ""


def _titleize(slug: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", slug) if part)


def normalize_template(raw: dict[str, Any]) -> AppTemplate:
    slug = str(raw.get("slug") or "")
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return AppTemplate(
        slug=slug,
        name=str(raw.get("name") or _titleize(slug)),
        description=str(raw.get("description") or ""),
        category=str(raw.get("category") or "other"),
        tags=[str(tag) for tag in tags],
        logo=str(raw.get("logo") or ""),
        port=str(raw.get("port") or ""),
        documentation=str(raw.get("documentation") or ""),
        compose_b64=str(raw.get("compose") or ""),
    )


@lru_cache(maxsize=1)
def load_catalog(path: Path = CATALOG_PATH) -> tuple[AppTemplate, ...]:
    """The shipped catalog, parsed once per process."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("templates") if isinstance(payload, dict) else None
    templates = [normalize_template(raw) for raw in entries or [] if isinstance(raw, dict)]
    templates = [t for t in templates if t.slug and t.compose_b64]
    templates.sort(key=lambda template: template.name.lower())
    return tuple(templates)


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
    """Make a catalog template runnable by plain `docker compose`.

    Templates may reference named volumes they never declare; plain compose requires
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
    """Read access to the shipped catalog (async to keep the service API unchanged)."""

    path: Path = CATALOG_PATH

    @classmethod
    def from_request(cls, request: Any = None) -> "AppCatalog":
        return cls()

    async def list_templates(self, refresh: bool = False) -> list[AppTemplate]:
        if refresh:
            load_catalog.cache_clear()
        return list(load_catalog(self.path))

    async def get_template(self, slug: str) -> AppTemplate | None:
        for template in await self.list_templates():
            if template.slug == slug:
                return template
        return None
