"""Builder — turns a git repo into a runnable OCI image (the zero-config deploy core).

Detection follows the universal rule: a **Dockerfile at the repo root wins** (built with Docker's
own BuildKit, already on the host); otherwise we shell out to **Nixpacks**, which inspects the
repo, generates a build, and produces a local image via the Docker daemon. Commands run through an
**injectable async runner**, so the whole thing is unit-testable without git/docker/nixpacks present
(mirrors app/services/docker_engine.py).
"""

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# (argv, cwd) -> (returncode, stdout, stderr)
CommandRunner = Callable[[list[str], str | None], Awaitable[tuple[int, str, str]]]
# per-output-line sink, awaited for each build line as it is produced
LineSink = Callable[[str], Awaitable[None]]
# (argv, cwd, sink) -> (returncode, combined_output) — streams each line to `sink` live
StreamRunner = Callable[[list[str], str | None, LineSink], Awaitable[tuple[int, str]]]

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


async def _default_stream_runner(
    argv: list[str], cwd: str | None, sink: LineSink
) -> tuple[int, str]:
    """Run ``argv`` and forward each output line to ``sink`` as it is produced.

    stderr is merged into stdout so build progress (docker/nixpacks write it there)
    streams in emission order. Returns ``(returncode, combined_output)`` — the joined
    output preserves the existing ``_exec`` error-detail behaviour.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    captured: list[str] = []
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        captured.append(line)
        await sink(line)
    rc = await proc.wait()
    return rc or 0, "\n".join(captured)


class Builder:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        stream_runner: StreamRunner | None = None,
        docker_bin: str = "docker",
        nixpacks_bin: str = "nixpacks",
        git_bin: str = "git",
        workdir: str = "/tmp/tetra-builds",
        github_token: str = "",
    ) -> None:
        self._run = runner or _default_runner
        self._stream = stream_runner or _default_stream_runner
        self.docker = docker_bin
        self.nixpacks = nixpacks_bin
        self.git = git_bin
        self.workdir = workdir.rstrip("/")
        self.github_token = github_token

    def _auth_url(self, git_url: str) -> str:
        """Inject the GitHub token so PRIVATE github.com HTTPS repos can clone. Other hosts and
        non-HTTPS URLs pass through untouched (SSH/public need no token)."""
        if self.github_token and git_url.startswith("https://github.com/"):
            return git_url.replace(
                "https://", f"https://x-access-token:{self.github_token}@", 1
            )
        return git_url

    def _scrub(self, text: str) -> str:
        """Never let the token reach a build log or error surface."""
        if not self.github_token:
            return text
        return text.replace(self.github_token, "***").replace("x-access-token:***@", "")

    async def _exec(
        self, argv: list[str], *, cwd: str | None = None, on_line: LineSink | None = None
    ) -> str:
        """Run a command. When ``on_line`` is given, stream each output line to it live
        (used for the long build step); otherwise capture and return the output."""
        try:
            if on_line is not None:
                rc, out = await self._stream(argv, cwd, on_line)
                err = ""
            else:
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
        """Shallow-clone ``ref`` of ``git_url`` into ``dest``; return the resolved commit SHA.

        Private github.com repos are authenticated with the configured token (never logged).
        A missing-credentials failure on an unauthenticated clone gets a clear hint."""
        url = self._auth_url(git_url)
        try:
            await self._exec([self.git, "clone", "--depth", "1", "--branch", ref, url, dest])
        except BuildError as exc:
            message = self._scrub(exc.message)
            if not self.github_token and "could not read Username" in exc.message:
                message = (
                    "Authentication required — this looks like a private repository. "
                    "Set GITHUB_TOKEN on the host (a PAT with repo:read) to deploy it. "
                    f"({message})"
                )
            logger.warning("git clone failed for %s@%s: %s", git_url, ref, message)
            raise BuildError(message=message, code=exc.code) from exc
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

    async def build(
        self, src_dir: str, image: str, *, on_line: LineSink | None = None
    ) -> BuildResult:
        """Build ``src_dir`` into ``image`` — Dockerfile if present, else Nixpacks.

        ``on_line`` (when given) receives each build-output line live, so the deploy
        can stream real build logs instead of freezing until the build finishes.
        """
        if await self._has_dockerfile(src_dir):
            await self._exec([self.docker, "build", "-t", image, src_dir], on_line=on_line)
            builder = "dockerfile"
        else:
            await self._exec([self.nixpacks, "build", src_dir, "--name", image], on_line=on_line)
            builder = "nixpacks"
        return BuildResult(image=image, builder=builder, port=await self.detect_port(image))

    async def build_from_git(
        self, git_url: str, ref: str, *, project: str, on_line: LineSink | None = None
    ) -> BuildResult:
        """Clone + build a git repo into an immutable ``tetra-<project>:<sha>`` image."""
        logger.info("building project '%s' from %s@%s", project, git_url, ref)
        dest = f"{self.workdir}/{project}"
        await self._exec(["rm", "-rf", dest])
        sha = await self.clone(git_url, ref, dest)
        tag = sha[:12] if sha else "latest"
        image = f"tetra-{project}:{tag}"
        result = await self.build(dest, image, on_line=on_line)
        result.commit = sha
        logger.info("built image %s via %s (commit %s)", result.image, result.builder, sha or "?")
        return result
