"""Edge service — publishes Tetra-managed app containers through Caddy.

caddy-docker-proxy watches the Docker socket and turns container **labels** into routes, so to
expose an installed app we attach Caddy labels to its public service and join it to a shared
external network that the Caddy container is also on. TLS for ``*.<apps_base_domain>`` is
terminated upstream by nginx (this box's public edge); Caddy routes by Host header to the app.

This is **opt-in**: only active when ``edge_network`` + ``apps_base_domain`` are configured, so
deploying the code with the infra absent is a safe no-op (apps deploy exactly as before).
"""

from typing import Any

import yaml

from app.config import get_settings


def edge_enabled() -> bool:
    settings = get_settings()
    return bool(settings.edge_network and settings.apps_base_domain)


def app_hostname(project: str) -> str:
    return f"{project}.{get_settings().apps_base_domain}"


def _labels_to_dict(labels: Any) -> dict[str, str]:
    """Compose labels may be a list ('k=v'/'k') or a map; normalize to a map."""
    if isinstance(labels, dict):
        return {str(k): "" if v is None else str(v) for k, v in labels.items()}
    result: dict[str, str] = {}
    if isinstance(labels, list):
        for item in labels:
            text = str(item)
            key, _, value = text.partition("=")
            result[key.strip()] = value.strip()
    return result


def _networks_with(networks: Any, name: str) -> list[str] | dict[str, Any]:
    """Add ``name`` to a service's networks (preserving list/dict shape)."""
    if isinstance(networks, dict):
        networks.setdefault(name, {})
        return networks
    items = list(networks) if isinstance(networks, list) else []
    if name not in items:
        items.append(name)
    return items


def _public_service(services: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Pick the web-facing service: the one whose env references SERVICE_FQDN_* (Coolify's
    convention for the public service), else the first service."""
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        env = svc.get("environment") or []
        env_text = " ".join(env) if isinstance(env, list) else " ".join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else ""
        if "SERVICE_FQDN_" in env_text:
            return name, svc
    for name, svc in services.items():
        if isinstance(svc, dict):
            return name, svc
    return None


def apply_edge(compose_yaml: str, *, project: str, port: str) -> str:
    """Attach Caddy routing labels + the shared edge network to a compose stack's public
    service. No-op (returns input unchanged) when the edge is not configured."""
    if not edge_enabled():
        return compose_yaml
    try:
        doc = yaml.safe_load(compose_yaml)
    except yaml.YAMLError:
        return compose_yaml
    if not isinstance(doc, dict):
        return compose_yaml

    services = doc.get("services") or {}
    chosen = _public_service(services)
    if not chosen:
        return compose_yaml
    _name, svc = chosen

    network = get_settings().edge_network
    host = app_hostname(project)
    upstream = f"{{{{upstreams {port}}}}}" if port else "{{upstreams}}"

    labels = _labels_to_dict(svc.get("labels"))
    # http:// scheme => Caddy serves this site HTTP-only (no ACME); nginx terminates the
    # wildcard TLS upstream and forwards plain HTTP to Caddy on the box's public edge.
    labels["caddy"] = f"http://{host}"
    labels["caddy.reverse_proxy"] = upstream
    svc["labels"] = labels

    svc["networks"] = _networks_with(svc.get("networks"), network)
    top_networks = doc.get("networks")
    if not isinstance(top_networks, dict):
        top_networks = {}
    top_networks[network] = {"external": True}
    doc["networks"] = top_networks

    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
