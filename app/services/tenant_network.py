"""Per-tenant private Docker network — how a tenant's apps reach its managed databases.

Each tenant gets one bridge network. Its databases join it under their own name, and its
git-deployed apps join it on deploy once the tenant has a database. Other tenants' containers
are never on it, so a database is reachable only by its owner's apps (the shared edge network
carries web traffic only and never has databases on it).
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)

NETWORK_KEY = "tetra-tenant"


def tenant_network_name(tenant_id: str | int | None) -> str:
    # Legacy rows may carry an integer id (production's first tenant is 1).
    slug = str(tenant_id or "platform").replace("-", "").lower()[:12] or "platform"
    return f"tetra-t-{slug}"


def _join(networks: Any, key: str) -> list[str] | dict[str, Any]:
    # A service with no explicit networks is on compose's "default"; keep it there.
    if isinstance(networks, dict):
        networks.setdefault(key, {})
        return networks
    items = list(networks) if isinstance(networks, list) and networks else ["default"]
    if key not in items:
        items.append(key)
    return items


def apply_tenant_network(compose_yaml: str, network: str) -> str:
    """Join every service of ``compose_yaml`` to the external tenant ``network``."""
    if not network:
        return compose_yaml
    try:
        doc = yaml.safe_load(compose_yaml)
    except yaml.YAMLError:
        logger.warning("tenant network skipped: compose YAML failed to parse")
        return compose_yaml
    if not isinstance(doc, dict) or not isinstance(doc.get("services"), dict):
        return compose_yaml
    for svc in doc["services"].values():
        if isinstance(svc, dict):
            svc["networks"] = _join(svc.get("networks"), NETWORK_KEY)
    top = doc.get("networks") if isinstance(doc.get("networks"), dict) else {}
    top[NETWORK_KEY] = {"name": network, "external": True}
    doc["networks"] = top
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
