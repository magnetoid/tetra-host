"""Tetra Engine — talks to the Docker Engine directly (no Coolify in the data path).

Container/stack lifecycle is driven through the ``docker`` / ``docker compose`` CLIs over an
**injectable async command runner**, so the engine is fully unit-testable in-process without a
running Docker daemon (mirrors how ``tetra_cli`` injects an httpx transport). The real runner
shells out to ``docker``; tests inject a fake runner that records argv/stdin and returns canned
output.
"""

import asyncio
import gzip
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# (argv, stdin, env) -> (returncode, stdout, stderr)
CommandRunner = Callable[[list[str], str | None, dict[str, str] | None], Awaitable[tuple[int, str, str]]]

# (argv, gzip file to stream into stdin, gzip file to write stdout into) -> (returncode, stderr)
PipeRunner = Callable[[list[str], str | None, str | None], Awaitable[tuple[int, str]]]

_CHUNK = 1 << 16

_PROJECT_SANITIZE = re.compile(r"[^a-z0-9_-]+")


@dataclass(slots=True)
class DockerEngineError(Exception):
    message: str
    code: int | None = None

    def __str__(self) -> str:
        return self.message


def sanitize_project_name(name: str) -> str:
    """Compose project names must be lowercase [a-z0-9_-], starting alphanumeric."""
    slug = _PROJECT_SANITIZE.sub("-", (name or "").strip().lower()).strip("-_")
    return slug or "app"


async def _default_runner(
    argv: list[str], stdin: str | None, env: dict[str, str] | None
) -> tuple[int, str, str]:
    import os

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE if stdin is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **(env or {})} if env else None,
    )
    out_b, err_b = await proc.communicate(stdin.encode() if stdin is not None else None)
    return proc.returncode or 0, out_b.decode("utf-8", "replace"), err_b.decode("utf-8", "replace")


async def _default_pipe_runner(
    argv: list[str], stdin_path: str | None, stdout_path: str | None
) -> tuple[int, str]:
    """Run ``argv`` streaming a gzip file into stdin and/or stdout into a gzip file.

    Streams in chunks, so a dump or restore never has to fit in memory.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE if stdin_path else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE if stdout_path else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    async def feed() -> None:
        assert proc.stdin is not None
        try:
            with gzip.open(stdin_path, "rb") as src:  # type: ignore[arg-type]
                while chunk := src.read(_CHUNK):
                    proc.stdin.write(chunk)
                    await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the process exited early; its exit code and stderr say why
        finally:
            proc.stdin.close()

    async def drain_out() -> None:
        assert proc.stdout is not None
        with gzip.open(stdout_path, "wb") as dst:  # type: ignore[arg-type]
            while chunk := await proc.stdout.read(_CHUNK):
                dst.write(chunk)

    async def read_err() -> bytes:
        assert proc.stderr is not None
        return await proc.stderr.read()

    tasks = [read_err()]
    if stdin_path:
        tasks.append(feed())
    if stdout_path:
        tasks.append(drain_out())
    try:
        results = await asyncio.gather(*tasks)
        await proc.wait()
    except asyncio.CancelledError:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    err = results[0] if isinstance(results[0], bytes) else b""
    return proc.returncode or 0, err.decode("utf-8", "replace")


def _parse_json_objects(text: str) -> list[dict[str, Any]]:
    """Parse `docker compose` JSON output — either a JSON array or newline-delimited objects."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass
    objects: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            objects.append(obj)
    return objects


class DockerEngine:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        pipe_runner: PipeRunner | None = None,
        docker_bin: str = "docker",
    ) -> None:
        self._run = runner or _default_runner
        self._pipe = pipe_runner or _default_pipe_runner
        self.docker = docker_bin

    async def _docker(
        self, *args: str, stdin: str | None = None, env: dict[str, str] | None = None
    ) -> str:
        try:
            rc, out, err = await self._run([self.docker, *args], stdin, env)
        except OSError as exc:  # docker binary missing / not reachable
            logger.warning("docker binary unavailable: %s", exc)
            raise DockerEngineError(message=f"Docker is not available: {exc}", code=503) from exc
        if rc != 0:
            detail = err.strip() or out.strip() or f"docker {args[0] if args else ''} failed"
            # 502 (bad gateway): docker ran but failed. NOTE: the subprocess exit code is
            # NOT an HTTP status — keep it in the message, never in `code`.
            raise DockerEngineError(message=f"{detail[:500]} (docker exit {rc})", code=502)
        return out

    async def is_available(self) -> bool:
        try:
            await self.version()
            return True
        except (DockerEngineError, FileNotFoundError, OSError):
            return False

    async def version(self) -> str:
        out = await self._docker("version", "--format", "{{.Server.Version}}")
        return out.strip()

    # ── Stack lifecycle (one compose project per installed app) ───────────

    async def deploy_stack(
        self, project: str, compose_yaml: str, env: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """`docker compose -p <project> -f - up -d` with the compose piped on stdin.

        ``env`` values are exposed to compose's ``${VAR}`` interpolation via the process env,
        which is how the rendered SERVICE_* secrets reach the template.
        """
        project = sanitize_project_name(project)
        logger.info("deploying compose stack %s", project)
        await self._docker(
            "compose", "-p", project, "-f", "-", "up", "-d", "--remove-orphans",
            stdin=compose_yaml, env=env,
        )
        return {"ok": True, "project": project}

    async def list_stacks(self) -> list[dict[str, Any]]:
        out = await self._docker("compose", "ls", "--all", "--format", "json")
        return _parse_json_objects(out)

    async def stack_ps(self, project: str) -> list[dict[str, Any]]:
        project = sanitize_project_name(project)
        out = await self._docker("compose", "-p", project, "ps", "--all", "--format", "json")
        return _parse_json_objects(out)

    async def start_stack(self, project: str) -> dict[str, Any]:
        project = sanitize_project_name(project)
        logger.info("starting compose stack %s", project)
        await self._docker("compose", "-p", project, "start")
        return {"ok": True, "project": project}

    async def stop_stack(self, project: str) -> dict[str, Any]:
        project = sanitize_project_name(project)
        logger.info("stopping compose stack %s", project)
        await self._docker("compose", "-p", project, "stop")
        return {"ok": True, "project": project}

    async def restart_stack(self, project: str) -> dict[str, Any]:
        project = sanitize_project_name(project)
        logger.info("restarting compose stack %s", project)
        await self._docker("compose", "-p", project, "restart")
        return {"ok": True, "project": project}

    async def stack_mounts(self, project: str) -> list[dict[str, Any]]:
        """Volumes and bind mounts of a stack's containers, one entry per mount.

        Host paths are left out on purpose: tenants see the volume name and where it is
        mounted inside the container, never the layout of the shared host.
        """
        containers = await self.stack_ps(project)
        ids = [str(c.get("ID") or c.get("Id") or "") for c in containers]
        ids = [cid for cid in ids if cid]
        if not ids:
            return []
        out = await self._docker("inspect", *ids)
        mounts: list[dict[str, Any]] = []
        for container in _parse_json_objects(out):
            labels = (container.get("Config") or {}).get("Labels") or {}
            service = str(labels.get("com.docker.compose.service") or "")
            for mount in container.get("Mounts") or []:
                kind = str(mount.get("Type") or "")
                mounts.append(
                    {
                        "service": service,
                        "type": kind,
                        "name": str(mount.get("Name") or "") if kind == "volume" else "",
                        "destination": str(mount.get("Destination") or ""),
                        "read_only": not bool(mount.get("RW", True)),
                    }
                )
        mounts.sort(key=lambda m: (m["service"], m["destination"]))
        return mounts

    async def remove_stack(self, project: str, *, volumes: bool = False) -> dict[str, Any]:
        project = sanitize_project_name(project)
        logger.info("removing compose stack %s (volumes=%s)", project, volumes)
        args = ["compose", "-p", project, "down", "--remove-orphans"]
        if volumes:
            args.append("--volumes")
        await self._docker(*args)
        return {"ok": True, "project": project}

    async def logs(self, project: str, *, tail: int = 200) -> str:
        project = sanitize_project_name(project)
        return await self._docker(
            "compose", "-p", project, "logs", "--no-color", "--tail", str(tail)
        )

    async def container_stats(self, container_ids: list[str]) -> list[dict[str, Any]]:
        """A one-shot `docker stats` snapshot (JSON) for specific containers."""
        ids = [cid for cid in container_ids if cid]
        if not ids:
            return []
        out = await self._docker(
            "stats", "--no-stream", "--no-trunc", "--format", "{{json .}}", *ids
        )
        return _parse_json_objects(out)

    async def stats_for_project(self, project: str) -> list[dict[str, Any]]:
        """Live per-container compute snapshot for a compose project (raw docker stats JSON)."""
        containers = await self.stack_ps(project)
        ids = [
            str(c.get("ID") or c.get("Id") or c.get("Name") or "")
            for c in containers
            if (c.get("ID") or c.get("Id") or c.get("Name"))
        ]
        return await self.container_stats(ids)

    # ── Networks ─────────────────────────────────────────────────────────

    async def ensure_network(self, name: str, *, labels: dict[str, str] | None = None) -> None:
        """Create a bridge network unless it already exists (idempotent)."""
        try:
            await self._docker("network", "inspect", name, "--format", "{{.Name}}")
            return
        except DockerEngineError as exc:
            if exc.code == 503:
                raise
        args = ["network", "create", "--driver", "bridge"]
        for key, value in (labels or {}).items():
            args += ["--label", f"{key}={value}"]
        try:
            await self._docker(*args, name)
        except DockerEngineError as exc:
            if "already exists" not in exc.message:
                raise
        logger.info("docker network %s ready", name)

    # ── Streaming exec (database dumps and restores) ─────────────────────

    async def _exec_piped(
        self, project: str, service: str, script: str, *,
        stdin_path: str | None = None, stdout_path: str | None = None,
    ) -> None:
        project = sanitize_project_name(project)
        argv = [self.docker, "compose", "-p", project, "exec", "-T", service, "sh", "-c", script]
        try:
            rc, err = await self._pipe(argv, stdin_path, stdout_path)
        except OSError as exc:
            raise DockerEngineError(message=f"Docker is not available: {exc}", code=503) from exc
        if rc != 0:
            detail = err.strip() or "command failed"
            raise DockerEngineError(message=f"{detail[-500:]} (exit {rc})", code=502)

    async def exec_to_gzip(self, project: str, service: str, script: str, path: str) -> None:
        """Run ``script`` in the service's container, writing its stdout gzipped to ``path``."""
        await self._exec_piped(project, service, script, stdout_path=path)

    async def exec_from_gzip(self, project: str, service: str, script: str, path: str) -> None:
        """Run ``script`` in the service's container with the gzip file ``path`` as stdin."""
        await self._exec_piped(project, service, script, stdin_path=path)
