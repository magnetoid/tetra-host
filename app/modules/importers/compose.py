"""Rewrite a Coolify-rendered compose project into a self-contained Tetra Engine stack.

Coolify writes each application's compose file and ``.env`` to
``/data/coolify/applications/<uuid>/``. That compose depends on Coolify: its external
network, Traefik/Caddy labels, uuid-suffixed container names, ``build:`` contexts on
disk, ``env_file: .env`` and ``${VAR}`` interpolation. This module turns it into a
plain compose document the engine can run with ``docker compose -f -``:

* every ``${...}`` is resolved here from the ``.env`` (never from the panel's own
  process environment), and literal ``$`` is re-escaped as ``$$``;
* ``env_file`` is folded into ``environment`` (``environment`` wins, as in compose);
* Coolify labels, ``container_name`` and external networks are dropped, and references
  to the old container names are rewritten to service names;
* ``build:`` is dropped in favour of the image Coolify already built;
* named volumes are renamed to the target project, bind mounts from the Coolify app
  directory are re-pointed at the engine's files directory;
* published host ports can be shifted (for a side-by-side trial copy) and services can
  be excluded (background workers that must not run twice).

Everything here is pure: no Docker, no I/O. ``ImportPlan`` lists what the host side
has to do (images to keep, volumes and files to copy, ports to probe).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import yaml

_COOLIFY_LABEL_PREFIXES = ("coolify.", "traefik.", "caddy")
_VAR_NAME = r"[A-Za-z_][A-Za-z0-9_]*"


class ComposeImportError(ValueError):
    """The source compose uses something the importer cannot carry over safely."""


@dataclass(frozen=True)
class PortMap:
    service: str
    host_ip: str
    host_port: int
    container_port: str
    protocol: str = "tcp"


@dataclass(frozen=True)
class VolumeMap:
    key: str
    source_name: str
    target_name: str


@dataclass(frozen=True)
class BindMap:
    service: str
    source_path: str
    rel_path: str
    target_path: str


@dataclass
class ImportPlan:
    services: list[str] = field(default_factory=list)
    locally_built: dict[str, str] = field(default_factory=dict)  # service -> image ref
    images: dict[str, str] = field(default_factory=dict)  # service -> image ref (as rewritten)
    ports: list[PortMap] = field(default_factory=list)
    volumes: list[VolumeMap] = field(default_factory=list)
    binds: list[BindMap] = field(default_factory=list)
    background: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── .env + interpolation ────────────────────────────────────────────────────


def parse_env_file(text: str) -> dict[str, str]:
    """Parse a dotenv file the way compose does for the common cases.

    Supports ``KEY=value``, ``export KEY=value``, comments and blank lines,
    single-quoted (literal) and double-quoted (``\\n``/``\\"``/``\\\\`` escapes) values.
    """
    env: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not re.fullmatch(_VAR_NAME, key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1]
        elif len(value) >= 2 and value[0] == value[-1] == '"':
            value = (
                value[1:-1]
                .replace("\\\\", "\0")
                .replace("\\n", "\n")
                .replace('\\"', '"')
                .replace("\0", "\\")
            )
        else:
            # Unquoted: an inline comment needs whitespace before '#'.
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        env[key] = value
    return env


def _find_closing(text: str, start: int) -> int:
    """Index of the '}' closing the '${' whose body starts at ``start``."""
    depth = 1
    i = start
    while i < len(text):
        if text.startswith("${", i):
            depth += 1
            i += 2
            continue
        if text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ComposeImportError(f"Unterminated '${{' in {text!r}")


def interpolate(text: str, env: dict[str, str], missing: set[str] | None = None) -> str:
    """Resolve compose-style interpolation against ``env`` only.

    Handles ``$$``, ``$VAR``, ``${VAR}``, ``${VAR:-d}``, ``${VAR-d}``, ``${VAR:+a}``,
    ``${VAR+a}``, ``${VAR:?e}``, ``${VAR?e}``, with nested interpolation in the
    default/alternative. Unset variables resolve to "" and are added to ``missing``.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch != "$":
            out.append(ch)
            i += 1
            continue
        if text.startswith("$$", i):
            out.append("$")
            i += 2
            continue
        if text.startswith("${", i):
            end = _find_closing(text, i + 2)
            body = text[i + 2 : end]
            match = re.match(rf"({_VAR_NAME})(:?[-+?])?(.*)\Z", body, re.S)
            if not match:
                raise ComposeImportError(f"Invalid interpolation '${{{body}}}'")
            name, op, rest = match.group(1), match.group(2), match.group(3)
            if op is None and rest:
                raise ComposeImportError(f"Invalid interpolation '${{{body}}}'")
            is_set = name in env
            value = env.get(name, "")
            empty = value == ""
            if op in (":-", "-"):
                use_default = not is_set or (op == ":-" and empty)
                out.append(interpolate(rest, env, missing) if use_default else value)
            elif op in (":+", "+"):
                use_alt = is_set and not (op == ":+" and empty)
                out.append(interpolate(rest, env, missing) if use_alt else "")
            elif op in (":?", "?"):
                if not is_set or (op == ":?" and empty):
                    raise ComposeImportError(
                        f"Required variable {name} is not set: {interpolate(rest, env)}"
                    )
                out.append(value)
            else:
                if not is_set and missing is not None:
                    missing.add(name)
                out.append(value)
            i = end + 1
            continue
        match = re.match(_VAR_NAME, text[i + 1 :])
        if match:
            name = match.group(0)
            if name not in env and missing is not None:
                missing.add(name)
            out.append(env.get(name, ""))
            i += 1 + len(name)
            continue
        out.append("$")
        i += 1
    return "".join(out)


def _map_strings(node: Any, fn) -> Any:
    if isinstance(node, str):
        return fn(node)
    if isinstance(node, list):
        return [_map_strings(item, fn) for item in node]
    if isinstance(node, dict):
        return {key: _map_strings(value, fn) for key, value in node.items()}
    return node


# ── per-key rewrites ─────────────────────────────────────────────────────────


def _environment_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): ("" if v is None else v) for k, v in value.items()}
    if isinstance(value, list):
        env: dict[str, Any] = {}
        for item in value:
            key, sep, val = str(item).partition("=")
            env[key] = val if sep else ""
        return env
    raise ComposeImportError("Unsupported 'environment' format")


def _filter_labels(labels: Any) -> Any:
    if isinstance(labels, dict):
        kept = {k: v for k, v in labels.items() if not str(k).startswith(_COOLIFY_LABEL_PREFIXES)}
        return kept or None
    if isinstance(labels, list):
        kept = [x for x in labels if not str(x).split("=", 1)[0].startswith(_COOLIFY_LABEL_PREFIXES)]
        return kept or None
    return labels


def _parse_port(service: str, entry: Any) -> PortMap | None:
    """Return the published mapping for a port entry (None for container-only ports)."""
    if isinstance(entry, dict):
        published = entry.get("published")
        if published in (None, ""):
            return None
        return PortMap(
            service=service,
            host_ip=str(entry.get("host_ip") or ""),
            host_port=int(str(published)),
            container_port=str(entry.get("target")),
            protocol=str(entry.get("protocol") or "tcp"),
        )
    spec = str(entry)
    protocol = "tcp"
    if "/" in spec:
        spec, protocol = spec.rsplit("/", 1)
    parts = spec.rsplit(":", 2) if not spec.startswith("[") else spec.split("]:", 1)
    if spec.startswith("["):  # [ipv6]:host:container
        host_ip = parts[0] + "]"
        host_port, _, container = parts[1].partition(":")
    elif len(parts) == 3:
        host_ip, host_port, container = parts
    elif len(parts) == 2:
        host_ip, (host_port, container) = "", parts
    else:
        return None
    if "-" in host_port:
        raise ComposeImportError(f"Port ranges are not supported ({service}: {entry})")
    return PortMap(service, host_ip, int(host_port), container, protocol)


def _format_port(port: PortMap, host_port: int) -> str:
    prefix = f"{port.host_ip}:" if port.host_ip else ""
    suffix = "" if port.protocol == "tcp" else f"/{port.protocol}"
    return f"{prefix}{host_port}:{port.container_port}{suffix}"


def _is_named_volume(source: str) -> bool:
    return bool(source) and not source.startswith(("/", ".", "~")) and "/" not in source


def _clean_volume_key(key: str, source_project: str) -> str:
    prefix = f"{source_project}_"
    return key[len(prefix):] if key.startswith(prefix) else key


def _rel_within(path: str, root: str) -> str | None:
    p, r = PurePosixPath(path), PurePosixPath(root)
    try:
        rel = p.relative_to(r)
    except ValueError:
        return None
    if ".." in rel.parts or not rel.parts:
        return None
    return rel.as_posix()


def _references(text: str, name: str) -> bool:
    return re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-])", text) is not None


def detect_background(services: dict[str, Any]) -> list[str]:
    """Services that publish no port and that no other service refers to.

    These are workers (mail senders, pollers, cron runners). A trial copy must not run
    them next to the live stack, or they would act twice on shared side effects.
    """
    def _without_coolify_env(svc: Any) -> Any:
        # Coolify injects SERVICE_NAME_*/SERVICE_URL_*/COOLIFY_* into every service; those
        # mention every sibling and say nothing about real dependencies.
        if not isinstance(svc, dict):
            return svc
        env = _environment_dict(svc.get("environment"))
        kept = {k: v for k, v in env.items() if not k.startswith(("SERVICE_", "COOLIFY_"))}
        return {**svc, "environment": kept}

    background: list[str] = []
    for name, svc in services.items():
        if not isinstance(svc, dict) or svc.get("ports"):
            continue
        others = yaml.safe_dump(
            {k: _without_coolify_env(v) for k, v in services.items() if k != name},
            sort_keys=True,
        )
        if not _references(others, name):
            background.append(name)
    return sorted(background)


# ── main entry point ─────────────────────────────────────────────────────────


def build_stack(
    source_yaml: str,
    env_text: str,
    *,
    source_project: str,
    source_dir: str,
    project: str,
    files_dir: str,
    port_offset: int = 0,
    exclude: tuple[str, ...] | list[str] = (),
    image_overrides: dict[str, str] | None = None,
) -> tuple[str, ImportPlan]:
    """Return ``(compose_yaml, plan)`` for running the source app as ``project``."""
    try:
        doc = yaml.safe_load(source_yaml)
    except yaml.YAMLError as exc:
        raise ComposeImportError(f"Source compose is not valid YAML: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("services"), dict):
        raise ComposeImportError("Source compose has no services.")

    env = parse_env_file(env_text)
    missing: set[str] = set()
    dollar_keys = sorted(k for k, v in env.items() if "$" in v)
    doc = _map_strings(doc, lambda s: interpolate(s, env, missing))
    plan = ImportPlan()
    if missing:
        plan.warnings.append(
            "Unset variables resolved to empty: " + ", ".join(sorted(missing))
        )
    if dollar_keys:
        plan.warnings.append(
            "These .env values contain '$' and are passed literally (compose may have "
            "interpolated them): " + ", ".join(dollar_keys)
        )

    services: dict[str, Any] = doc["services"]
    top_networks: dict[str, Any] = doc.get("networks") or {}
    top_volumes: dict[str, Any] = doc.get("volumes") or {}
    external_networks = {
        name for name, spec in top_networks.items() if isinstance(spec, dict) and spec.get("external")
    }
    plan.background = detect_background(services)
    excluded = sorted(set(exclude))
    unknown = [name for name in excluded if name not in services]
    if unknown:
        raise ComposeImportError(f"Cannot exclude unknown services: {', '.join(unknown)}")
    plan.excluded = excluded

    container_names: dict[str, str] = {}
    used_volume_keys: set[str] = set()
    overrides = image_overrides or {}

    for name, svc in services.items():
        if not isinstance(svc, dict):
            raise ComposeImportError(f"Service {name} is not a mapping.")
        if svc.get("container_name"):
            container_names[str(svc.pop("container_name"))] = name

        if "build" in svc:
            svc.pop("build")
            if not svc.get("image"):
                raise ComposeImportError(
                    f"Service {name} is built from source but has no image tag to reuse."
                )
            plan.locally_built[name] = str(svc["image"])
        if name in overrides:
            svc["image"] = overrides[name]
        if not svc.get("image"):
            raise ComposeImportError(f"Service {name} has no image.")
        plan.images[name] = str(svc["image"])

        if "labels" in svc:
            labels = _filter_labels(svc["labels"])
            if labels:
                svc["labels"] = labels
            else:
                svc.pop("labels")

        if "env_file" in svc:
            env_files = svc.pop("env_file")
            env_files = env_files if isinstance(env_files, list) else [env_files]
            for entry in env_files:
                path = entry.get("path") if isinstance(entry, dict) else entry
                rel = _rel_within(str(path), source_dir) if str(path).startswith("/") else None
                if str(path) not in (".env", "./.env") and rel != ".env":
                    raise ComposeImportError(
                        f"Service {name} uses env_file {path!r}; only the app's .env is supported."
                    )
            merged: dict[str, Any] = dict(env)
            merged.update(_environment_dict(svc.get("environment")))
            svc["environment"] = merged
        elif "environment" in svc:
            svc["environment"] = _environment_dict(svc["environment"])

        nets = svc.get("networks")
        if isinstance(nets, dict):
            nets = {k: v for k, v in nets.items() if k not in external_networks}
        elif isinstance(nets, list):
            nets = [n for n in nets if n not in external_networks]
        if nets is not None:
            if nets:
                svc["networks"] = nets
            else:
                svc.pop("networks")
        if svc.get("network_mode"):
            plan.warnings.append(f"{name}: network_mode {svc['network_mode']!r} kept as-is")

        new_volumes: list[Any] = []
        for entry in svc.get("volumes") or []:
            if isinstance(entry, dict):
                source = str(entry.get("source") or "")
                kind = entry.get("type", "volume")
            else:
                source = str(entry).split(":", 1)[0]
                kind = "volume" if _is_named_volume(source) else "bind"
            if kind == "volume" and _is_named_volume(source):
                key = _clean_volume_key(source, source_project)
                used_volume_keys.add(source)
                if isinstance(entry, dict):
                    entry = {**entry, "source": key}
                else:
                    entry = key + str(entry)[len(source):]
                new_volumes.append(entry)
                continue
            if kind == "bind":
                host = source
                if host.startswith("./"):
                    host = f"{source_dir.rstrip('/')}/{host[2:]}"
                rel = _rel_within(host, source_dir)
                if rel is None:
                    plan.warnings.append(f"{name}: bind mount {source!r} is outside the app dir; kept")
                    new_volumes.append(entry)
                    continue
                target = f"{files_dir.rstrip('/')}/{rel}"
                plan.binds.append(BindMap(name, host, rel, target))
                if isinstance(entry, dict):
                    entry = {**entry, "source": target}
                else:
                    entry = target + str(entry)[len(source):]
                new_volumes.append(entry)
                continue
            new_volumes.append(entry)
        if new_volumes:
            svc["volumes"] = new_volumes

        new_ports: list[Any] = []
        for entry in svc.get("ports") or []:
            port = _parse_port(name, entry)
            if port is None:
                new_ports.append(entry)
                continue
            if not port.host_ip or port.host_ip in ("0.0.0.0", "::", "[::]"):
                plan.warnings.append(
                    f"{name}: port {port.host_port} is published on all interfaces"
                )
            plan.ports.append(port)
            new_ports.append(_format_port(port, port.host_port + port_offset))
        if new_ports:
            svc["ports"] = new_ports

    for name in excluded:
        services.pop(name, None)
    plan.ports = [p for p in plan.ports if p.service not in excluded]
    plan.binds = [b for b in plan.binds if b.service not in excluded]
    for svc in services.values():
        deps = svc.get("depends_on")
        if isinstance(deps, dict):
            deps = {k: v for k, v in deps.items() if k not in excluded}
        elif isinstance(deps, list):
            deps = [d for d in deps if d not in excluded]
        if deps is not None:
            if deps:
                svc["depends_on"] = deps
            else:
                svc.pop("depends_on")

    # Old uuid-suffixed container names become service names (service DNS still works).
    if container_names:
        pattern = re.compile("|".join(re.escape(n) for n in sorted(container_names, key=len, reverse=True)))
        doc["services"] = _map_strings(services, lambda s: pattern.sub(lambda m: container_names[m.group(0)], s))
        services = doc["services"]

    # Top-level volumes: only those still referenced, renamed into the target project.
    still_used = {
        _clean_volume_key(src, source_project)
        for src in used_volume_keys
    }
    referenced_now: set[str] = set()
    for svc in services.values():
        for entry in svc.get("volumes") or []:
            src = entry.get("source") if isinstance(entry, dict) else str(entry).split(":", 1)[0]
            if src in still_used:
                referenced_now.add(src)
    new_top_volumes: dict[str, Any] = {}
    for src in sorted(used_volume_keys):
        key = _clean_volume_key(src, source_project)
        if key not in referenced_now:
            continue
        spec = top_volumes.get(src) or top_volumes.get(key) or {}
        if isinstance(spec, dict) and spec.get("external"):
            raise ComposeImportError(f"Volume {src} is external; copy it by hand first.")
        source_name = (spec or {}).get("name") or f"{source_project}_{src}"
        target_name = f"{project}_{key}"
        plan.volumes.append(VolumeMap(key=key, source_name=str(source_name), target_name=target_name))
        new_top_volumes[key] = {"name": target_name}
    if new_top_volumes:
        doc["volumes"] = new_top_volumes
    else:
        doc.pop("volumes", None)

    kept_networks = {k: v for k, v in top_networks.items() if k not in external_networks}
    if kept_networks:
        doc["networks"] = kept_networks
    else:
        doc.pop("networks", None)

    plan.services = sorted(services)
    doc = _map_strings(doc, lambda s: s.replace("$", "$$"))
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=4096), plan
