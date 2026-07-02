"""Container resource limits — cgroup v2 hard caps for tenant stacks.

Injects ``cpus`` / ``mem_limit`` / ``pids_limit`` into every service of a compose stack
so a tenant workload cannot starve the shared host (weight-based sharing only bites under
contention; these are absolute caps). v1 semantics: each service gets the app's full
allocation as its upper bound — simple, legible, and closes the unbounded-noisy-neighbor
hole; per-service partitioning can come with real metering. A template's own (stricter)
limits are preserved: we only fill gaps, never override.
"""

import yaml

from app.config import get_settings


def apply_resource_limits(
    compose_yaml: str,
    *,
    cpu_millicores: int,
    mem_mb: int,
    pids_limit: int | None = None,
) -> str:
    """Return ``compose_yaml`` with hard caps on every service (0/None field = skip)."""
    try:
        doc = yaml.safe_load(compose_yaml)
    except yaml.YAMLError:
        return compose_yaml
    if not isinstance(doc, dict):
        return compose_yaml
    services = doc.get("services")
    if not isinstance(services, dict):
        return compose_yaml

    pids = pids_limit if pids_limit is not None else get_settings().default_app_pids_limit
    for svc in services.values():
        if not isinstance(svc, dict):
            continue
        if cpu_millicores and "cpus" not in svc and "cpu_count" not in svc:
            svc["cpus"] = round(cpu_millicores / 1000, 3)
        if mem_mb and "mem_limit" not in svc:
            svc["mem_limit"] = f"{mem_mb}m"
        if pids and "pids_limit" not in svc:
            svc["pids_limit"] = pids

    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
