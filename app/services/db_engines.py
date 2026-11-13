"""Database engine specs for managed databases: image, compose, credentials, dump and restore.

Pure functions over plain data, so every engine is unit-testable without Docker. Dump and
restore scripts run inside the database container (``sh -c``) and read credentials from the
container's own environment, so passwords never appear on a command line.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from urllib.parse import quote

import yaml

SERVICE = "db"
TENANT_NETWORK_KEY = "tenant"

_NAME = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
# Names other containers on the tenant network already answer to.
_RESERVED_NAMES = {"app", "db", "localhost", "host", "gateway"}
_VERSION = re.compile(r"^[0-9][0-9a-z.]{0,15}$")


@dataclass(frozen=True, slots=True)
class EngineSpec:
    key: str
    label: str
    image: str  # format string with {version}
    default_version: str
    versions: tuple[str, ...]
    port: int
    data_path: str
    scheme: str
    supports_backup: bool


ENGINES: dict[str, EngineSpec] = {
    "postgres": EngineSpec(
        key="postgres", label="PostgreSQL", image="postgres:{version}-alpine",
        default_version="17", versions=("17", "16", "15"), port=5432,
        data_path="/var/lib/postgresql/data", scheme="postgresql", supports_backup=True,
    ),
    "mysql": EngineSpec(
        key="mysql", label="MySQL", image="mysql:{version}",
        default_version="8.4", versions=("8.4", "8.0"), port=3306,
        data_path="/var/lib/mysql", scheme="mysql", supports_backup=True,
    ),
    "mariadb": EngineSpec(
        key="mariadb", label="MariaDB", image="mariadb:{version}",
        default_version="11.4", versions=("11.4", "10.11"), port=3306,
        data_path="/var/lib/mysql", scheme="mysql", supports_backup=True,
    ),
    "redis": EngineSpec(
        key="redis", label="Redis", image="redis:{version}-alpine",
        default_version="7", versions=("7",), port=6379,
        data_path="/data", scheme="redis", supports_backup=False,
    ),
}


class InvalidDatabaseSpec(ValueError):
    pass


def validate_name(name: str) -> str:
    name = (name or "").strip().lower()
    if not _NAME.match(name) or "--" in name:
        raise InvalidDatabaseSpec(
            "Name must be 3-32 characters: lowercase letters, digits and single hyphens, "
            "starting with a letter."
        )
    if name in _RESERVED_NAMES:
        raise InvalidDatabaseSpec(f"'{name}' is reserved; pick another name.")
    return name


def resolve_engine(engine: str, version: str | None) -> tuple[EngineSpec, str]:
    spec = ENGINES.get((engine or "").strip().lower())
    if spec is None:
        raise InvalidDatabaseSpec(f"Unknown engine '{engine}'. Choose one of: {', '.join(ENGINES)}.")
    version = (version or "").strip() or spec.default_version
    if version not in spec.versions or not _VERSION.match(version):
        raise InvalidDatabaseSpec(
            f"{spec.label} version '{version}' is not offered. Choose one of: "
            f"{', '.join(spec.versions)}."
        )
    return spec, version


def _password() -> str:
    # URL-safe so a connection URL needs no escaping in most clients.
    return secrets.token_urlsafe(24)


def new_credentials(spec: EngineSpec, name: str) -> dict[str, str]:
    database = name.replace("-", "_")
    if spec.key == "redis":
        return {"password": _password()}
    creds = {"user": database, "password": _password(), "database": database}
    if spec.key in {"mysql", "mariadb"}:
        creds["root_password"] = _password()
    return creds


def container_env(spec: EngineSpec, creds: dict[str, str]) -> dict[str, str]:
    if spec.key == "postgres":
        return {
            "POSTGRES_USER": creds["user"],
            "POSTGRES_PASSWORD": creds["password"],
            "POSTGRES_DB": creds["database"],
        }
    if spec.key == "mysql":
        return {
            "MYSQL_ROOT_PASSWORD": creds["root_password"],
            "MYSQL_DATABASE": creds["database"],
            "MYSQL_USER": creds["user"],
            "MYSQL_PASSWORD": creds["password"],
        }
    if spec.key == "mariadb":
        return {
            "MARIADB_ROOT_PASSWORD": creds["root_password"],
            "MARIADB_DATABASE": creds["database"],
            "MARIADB_USER": creds["user"],
            "MARIADB_PASSWORD": creds["password"],
        }
    return {"REDIS_PASSWORD": creds["password"]}


def _healthcheck(spec: EngineSpec) -> list[str]:
    if spec.key == "postgres":
        return ["CMD-SHELL", 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"']
    if spec.key == "mysql":
        return ["CMD-SHELL", 'MYSQL_PWD="$$MYSQL_ROOT_PASSWORD" mysqladmin ping -uroot -h 127.0.0.1']
    if spec.key == "mariadb":
        return ["CMD-SHELL", "healthcheck.sh --connect --innodb_initialized"]
    return ["CMD-SHELL", 'redis-cli -a "$$REDIS_PASSWORD" --no-auth-warning ping | grep -q PONG']


def compose_for_database(
    spec: EngineSpec,
    version: str,
    *,
    name: str,
    creds: dict[str, str],
    network: str,
    cpu_millicores: int = 0,
    mem_mb: int = 0,
) -> str:
    """One-service compose: the database on the tenant network as ``name``, data on a volume.

    No ports are published: only the tenant's own apps can reach the database.
    """
    service: dict = {
        "image": spec.image.format(version=version),
        "restart": "unless-stopped",
        "environment": container_env(spec, creds),
        "volumes": [f"data:{spec.data_path}"],
        "networks": {TENANT_NETWORK_KEY: {"aliases": [name]}},
        "healthcheck": {
            "test": _healthcheck(spec),
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
        },
        "labels": {"tetra.database": name},
    }
    if spec.key == "redis":
        service["command"] = [
            "sh", "-c", 'exec redis-server --requirepass "$$REDIS_PASSWORD" --appendonly yes',
        ]
    if cpu_millicores:
        service["cpus"] = round(cpu_millicores / 1000, 3)
    if mem_mb:
        service["mem_limit"] = f"{mem_mb}m"
    doc = {
        "services": {SERVICE: service},
        "volumes": {"data": {}},
        "networks": {TENANT_NETWORK_KEY: {"name": network, "external": True}},
    }
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def connection_url(spec: EngineSpec, *, host: str, creds: dict[str, str]) -> str:
    password = quote(creds["password"], safe="")
    if spec.key == "redis":
        return f"redis://:{password}@{host}:{spec.port}/0"
    user = quote(creds["user"], safe="")
    return f"{spec.scheme}://{user}:{password}@{host}:{spec.port}/{creds['database']}"


def dump_script(spec: EngineSpec) -> str:
    """Shell run in the container; writes a plain SQL dump to stdout."""
    if spec.key == "postgres":
        return (
            'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
            "--clean --if-exists --no-owner --no-privileges"
        )
    if spec.key == "mysql":
        return (
            'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction '
            '--routines --triggers --no-tablespaces --databases "$MYSQL_DATABASE"'
        )
    if spec.key == "mariadb":
        return (
            'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump -uroot --single-transaction '
            '--routines --triggers --databases "$MARIADB_DATABASE"'
        )
    raise InvalidDatabaseSpec(f"{spec.label} backups are not supported yet.")


def restore_script(spec: EngineSpec) -> str:
    """Shell run in the container; reads the SQL dump from stdin."""
    if spec.key == "postgres":
        return 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q'
    if spec.key == "mysql":
        return 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot'
    if spec.key == "mariadb":
        return 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot'
    raise InvalidDatabaseSpec(f"{spec.label} restores are not supported yet.")
