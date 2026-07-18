"""Edge service — publishes Tetra-managed app containers through Caddy.

caddy-docker-proxy watches the Docker socket and turns container **labels** into routes, so to
expose an installed app we attach Caddy labels to its public service and join it to a shared
external network that the Caddy container is also on. TLS for ``*.<apps_base_domain>`` is
terminated upstream by nginx (this box's public edge); Caddy routes by Host header to the app.

This is **opt-in**: only active when ``edge_network`` + ``apps_base_domain`` are configured, so
deploying the code with the infra absent is a safe no-op (apps deploy exactly as before).
"""

import logging
from typing import Any

import yaml

from app.config import get_settings

logger = logging.getLogger(__name__)


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
    """Add ``name`` to a service's networks, preserving existing connectivity.

    Crucial: a service with no ``networks:`` key is implicitly on the compose ``default``
    network (how it reaches sibling services like its DB). Once we add an explicit network we
    must re-list ``default`` too, or the service silently loses access to its siblings.
    """
    if isinstance(networks, dict):
        networks.setdefault(name, {})
        return networks
    if isinstance(networks, list) and networks:
        items = list(networks)
    else:
        items = ["default"]
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


def apply_edge(
    compose_yaml: str, *, project: str, port: str, extra_hosts: list[str] | None = None
) -> str:
    """Attach Caddy routing labels + the shared edge network to a compose stack's public
    service. ``extra_hosts`` (verified custom domains) are added as additional site
    addresses on the same route. No-op (returns input unchanged) when the edge is not
    configured."""
    if not edge_enabled():
        return compose_yaml
    try:
        doc = yaml.safe_load(compose_yaml)
    except yaml.YAMLError:
        logger.warning("edge routing skipped for project %s: compose YAML failed to parse", project)
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
    # We run caddy-docker-proxy with a CUSTOM label prefix ("tetra") so it ONLY ever reads
    # our labels — never the `caddy.*` labels other tenants' containers carry on this shared
    # box. http:// => Caddy serves HTTP-only (no ACME); nginx terminates the wildcard TLS.
    # Verified custom domains ride the same site block as extra comma-separated addresses.
    addresses = [f"http://{host}"] + [f"http://{h}" for h in (extra_hosts or []) if h]
    labels["tetra"] = ", ".join(addresses)
    labels["tetra.reverse_proxy"] = upstream
    svc["labels"] = labels

    logger.info(
        "edge route attached for project %s: %s (+%d custom host(s))",
        project, host, len(extra_hosts or []),
    )
    svc["networks"] = _networks_with(svc.get("networks"), network)
    top_networks = doc.get("networks")
    if not isinstance(top_networks, dict):
        top_networks = {}
    top_networks[network] = {"external": True}
    doc["networks"] = top_networks

    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
