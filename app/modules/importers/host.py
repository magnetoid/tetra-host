"""Host-side operations for imports, done through short-lived helper containers.

The panel runs unprivileged (systemd ``ProtectSystem=full``) but is in the ``docker``
group. Coolify's app directory is root-only (mode 0700), so files and volumes are read
and copied by ``docker run --rm`` helpers instead of direct filesystem access. Paths and
names are always passed as separate argv items (never interpolated into a shell string).
"""

from __future__ import annotations

import asyncio
import re
from pathlib import PurePosixPath

import httpx

from app.services.docker_engine import DockerEngine, DockerEngineError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]*$")


def _check_name(value: str) -> str:
    if not _SAFE_NAME.match(value or ""):
        raise DockerEngineError(message=f"Unsafe volume name {value!r}", code=400)
    return value


def _check_ref(value: str) -> str:
    if not _SAFE_REF.match(value or ""):
        raise DockerEngineError(message=f"Unsafe image reference {value!r}", code=400)
    return value


def _check_rel(rel: str) -> str:
    path = PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise DockerEngineError(message=f"Unsafe relative path {rel!r}", code=400)
    return path.as_posix()


def _check_dir(path: str) -> str:
    p = PurePosixPath(path)
    if not p.is_absolute() or ".." in p.parts or ":" in path:
        raise DockerEngineError(message=f"Unsafe host directory {path!r}", code=400)
    return p.as_posix()


class HostOps:
    def __init__(self, engine: DockerEngine, *, helper_image: str) -> None:
        self.engine = engine
        self.helper_image = _check_ref(helper_image)

    async def _run(self, *mounts_and_cmd: str) -> str:
        return await self.engine._docker("run", "--rm", "--network", "none", *mounts_and_cmd)

    async def read_file(self, host_dir: str, rel: str, *, missing_ok: bool = False) -> str:
        host_dir, rel = _check_dir(host_dir), _check_rel(rel)
        try:
            return await self._run(
                "-v", f"{host_dir}:/src:ro", self.helper_image, "cat", f"/src/{rel}"
            )
        except DockerEngineError:
            if missing_ok:
                return ""
            raise

    async def copy_files(self, src_dir: str, rels: list[str], dst_dir: str) -> None:
        if not rels:
            return
        src_dir, dst_dir = _check_dir(src_dir), _check_dir(dst_dir)
        safe = [_check_rel(r) for r in rels]
        script = (
            'set -e; for f in "$@"; do mkdir -p "/dst/$(dirname "$f")"; '
            'cp -a "/src/$f" "/dst/$f"; done'
        )
        await self._run(
            "-v", f"{src_dir}:/src:ro", "-v", f"{dst_dir}:/dst",
            self.helper_image, "sh", "-c", script, "sh", *safe,
        )

    async def volume_exists(self, name: str) -> bool:
        try:
            await self.engine._docker("volume", "inspect", _check_name(name))
            return True
        except DockerEngineError:
            return False

    async def volume_size(self, name: str) -> int | None:
        if not await self.volume_exists(name):
            return None
        out = await self._run("-v", f"{_check_name(name)}:/v:ro", self.helper_image, "du", "-sk", "/v")
        try:
            return int(out.split()[0]) * 1024
        except (IndexError, ValueError):
            return None

    async def copy_volume(self, source: str, target: str) -> None:
        """Replace ``target``'s contents with an exact copy of ``source`` (ownership kept)."""
        source, target = _check_name(source), _check_name(target)
        if source == target:
            raise DockerEngineError(message="Refusing to copy a volume onto itself", code=400)
        if not await self.volume_exists(source):
            raise DockerEngineError(message=f"Source volume {source} does not exist", code=404)
        await self.engine._docker("volume", "create", target)
        script = "set -e; find /to -mindepth 1 -delete; cp -a /from/. /to/"
        await self._run(
            "-v", f"{source}:/from:ro", "-v", f"{target}:/to",
            self.helper_image, "sh", "-c", script,
        )

    async def remove_volume(self, name: str) -> None:
        if await self.volume_exists(name):
            await self.engine._docker("volume", "rm", _check_name(name))

    async def image_exists(self, ref: str) -> bool:
        try:
            await self.engine._docker("image", "inspect", "--format", "{{.Id}}", _check_ref(ref))
            return True
        except DockerEngineError:
            return False

    async def tag_image(self, source: str, target: str) -> None:
        await self.engine._docker("tag", _check_ref(source), _check_ref(target))

    async def coolify_proxy_url(self) -> str | None:
        """Loopback HTTPS address of Coolify's Traefik (``docker port coolify-proxy 443``)."""
        try:
            out = await self.engine._docker("port", "coolify-proxy", "443/tcp")
        except DockerEngineError:
            return None
        for line in out.splitlines():
            addr = line.strip()
            if addr.startswith("0.0.0.0:"):
                addr = "127.0.0.1:" + addr.split(":", 1)[1]
            if re.fullmatch(r"127\.0\.0\.1:\d+", addr):
                return f"https://{addr}"
        return None


def _vhost_headers(vhost: str | None) -> dict[str, str]:
    # The app sits behind TLS-terminating proxies; say so, or it may redirect to https.
    return {"Host": vhost, "X-Forwarded-Proto": "https"} if vhost else {}


async def probe_port(
    port: int, *, vhost: str | None = None, host: str = "127.0.0.1", timeout: float = 5.0
) -> str:
    """Classify what answers on a local port: ``http:<status>``, ``tcp`` or ``closed``.

    ``vhost`` sends that Host header (for apps that only answer their own hostnames).
    """
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, asyncio.TimeoutError):
        return "closed"
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"http://{host}:{port}/", headers=_vhost_headers(vhost), follow_redirects=False
            )
        return f"http:{response.status_code}"
    except httpx.HTTPError:
        return "tcp"


async def probe_upstream(url: str, vhost: str, *, timeout: float = 10.0) -> str:
    """What ``vhost`` answers through a local proxy (Coolify's Traefik): ``http:<status>``."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:  # noqa: S501 — loopback
            response = await client.get(
                f"{url.rstrip('/')}/", headers=_vhost_headers(vhost), follow_redirects=False
            )
        return f"http:{response.status_code}"
    except httpx.HTTPError:
        return "closed"
