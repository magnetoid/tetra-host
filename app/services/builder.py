"""Builder — turns a git repo into a runnable OCI image (the zero-config deploy core).

Detection follows the universal rule: a **Dockerfile at the repo root wins** (built with Docker's
own BuildKit, already on the host); otherwise we shell out to **Nixpacks**, which inspects the
repo, generates a build, and produces a local image via the Docker daemon. Commands run through an
**injectable async runner**, so the whole thing is unit-testable without git/docker/nixpacks present
(mirrors app/services/docker_engine.py).
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# (argv, cwd) -> (returncode, stdout, stderr)
CommandRunner = Callable[[list[str], str | None], Awaitable[tuple[int, str, str]]]

_SHA = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(slots=True)
class BuildError(Exception):
    message: str
    code: int | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class BuildResult:
    image: str
    builder: str  # "dockerfile" | "nixpacks"
    commit: str = ""
    port: int = 0  # detected from the image's EXPOSE, 0 if none


async def _default_runner(argv: list[str], cwd: str | None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    return proc.returncode or 0, out_b.decode("utf-8", "replace"), err_b.decode("utf-8", "replace")


class Builder:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        docker_bin: str = "docker",
        nixpacks_bin: str = "nixpacks",
        git_bin: str = "git",
        workdir: str = "/tmp/tetra-builds",
    ) -> None:
        self._run = runner or _default_runner
        self.docker = docker_bin
        self.nixpacks = nixpacks_bin
        self.git = git_bin
        self.workdir = workdir.rstrip("/")

    async def _exec(self, argv: list[str], *, cwd: str | None = None) -> str:
        try:
            rc, out, err = await self._run(argv, cwd)
        except OSError as exc:
            raise BuildError(message=f"{argv[0]} not available: {exc}", code=503) from exc
        if rc != 0:
            detail = (err.strip() or out.strip() or f"{argv[0]} failed")[:500]
            raise BuildError(message=f"{detail} (exit {rc})", code=502)
        return out

    async def _has_dockerfile(self, src_dir: str) -> bool:
        rc, _, _ = await self._run(["test", "-f", f"{src_dir}/Dockerfile"], None)
        return rc == 0

    async def clone(self, git_url: str, ref: str, dest: str) -> str:
        """Shallow-clone ``ref`` of ``git_url`` into ``dest``; return the resolved commit SHA."""
        await self._exec([self.git, "clone", "--depth", "1", "--branch", ref, git_url, dest])
        out = await self._exec([self.git, "-C", dest, "rev-parse", "HEAD"])
        sha = out.strip()
        return sha if _SHA.match(sha) else ""

    async def detect_port(self, image: str) -> int:
        """Read the first EXPOSE port from a built image (0 if none declared)."""
        out = await self._exec([self.docker, "inspect", "--format", "{{json .Config.ExposedPorts}}", image])
        try:
            ports = json.loads(out.strip() or "null")
        except json.JSONDecodeError:
            return 0
        if not isinstance(ports, dict):
            return 0
        for key in ports:
            number = str(key).split("/")[0]
            if number.isdigit():
                return int(number)
        return 0

    async def build(self, src_dir: str, image: str) -> BuildResult:
        """Build ``src_dir`` into ``image`` — Dockerfile if present, else Nixpacks."""
        if await self._has_dockerfile(src_dir):
            await self._exec([self.docker, "build", "-t", image, src_dir])
            builder = "dockerfile"
        else:
            await self._exec([self.nixpacks, "build", src_dir, "--name", image])
            builder = "nixpacks"
        return BuildResult(image=image, builder=builder, port=await self.detect_port(image))

    async def build_from_git(self, git_url: str, ref: str, *, project: str) -> BuildResult:
        """Clone + build a git repo into an immutable ``tetra-<project>:<sha>`` image."""
        dest = f"{self.workdir}/{project}"
        await self._exec(["rm", "-rf", dest])
        sha = await self.clone(git_url, ref, dest)
        tag = sha[:12] if sha else "latest"
        image = f"tetra-{project}:{tag}"
        result = await self.build(dest, image)
        result.commit = sha
        return result
