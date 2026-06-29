"""Tetra Engine — talks to the Docker Engine directly (no Coolify in the data path).

Container/stack lifecycle is driven through the ``docker`` / ``docker compose`` CLIs over an
**injectable async command runner**, so the engine is fully unit-testable in-process without a
running Docker daemon (mirrors how ``tetra_cli`` injects an httpx transport). The real runner
shells out to ``docker``; tests inject a fake runner that records argv/stdin and returns canned
output.
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

# (argv, stdin, env) -> (returncode, stdout, stderr)
CommandRunner = Callable[[list[str], str | None, dict[str, str] | None], Awaitable[tuple[int, str, str]]]

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
        docker_bin: str = "docker",
    ) -> None:
        self._run = runner or _default_runner
        self.docker = docker_bin

    async def _docker(
        self, *args: str, stdin: str | None = None, env: dict[str, str] | None = None
    ) -> str:
        try:
            rc, out, err = await self._run([self.docker, *args], stdin, env)
        except OSError as exc:  # docker binary missing / not reachable
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
        await self._docker("compose", "-p", project, "start")
        return {"ok": True, "project": project}

    async def stop_stack(self, project: str) -> dict[str, Any]:
        project = sanitize_project_name(project)
        await self._docker("compose", "-p", project, "stop")
        return {"ok": True, "project": project}

    async def remove_stack(self, project: str, *, volumes: bool = False) -> dict[str, Any]:
        project = sanitize_project_name(project)
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
