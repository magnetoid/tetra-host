"""Image registry — push built images so rollback survives local eviction (ADR 0014).

Config-gated on REGISTRY_URL (empty ⇒ disabled: images stay local-only, exactly the
pre-registry behavior). When set (host:port, e.g. ``127.0.0.1:5000``), every successful
non-preview build is tagged ``{registry}/{image}`` and pushed, and THAT ref is recorded
on the Deployment — so a later rollback can ``docker pull`` the image even after it was
pruned from the host. Docker CLI calls run through the same injectable async runner
pattern as Builder/DockerEngine; registry-side manifest deletion (retention) talks the
OCI distribution V2 HTTP API through an injectable httpx client.

Note: deleting a manifest only unlinks it — blob space is reclaimed by the registry's
offline ``garbage-collect`` (see scripts/install-registry.sh).
"""

import asyncio
import logging

import httpx

# (argv, cwd) -> (returncode, stdout, stderr) — mirrors app/services/builder.py
from app.services.builder import CommandRunner

logger = logging.getLogger(__name__)

_MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
    ]
)


def is_registry_qualified(image: str) -> bool:
    """True if ``image`` carries a registry prefix. Builder-local names are always
    ``tetra-<project>:<tag>`` — no slash — so a slash means registry-qualified."""
    return "/" in image


async def _default_runner(argv: list[str], cwd: str | None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    return proc.returncode or 0, out_b.decode("utf-8", "replace"), err_b.decode("utf-8", "replace")


class ImageRegistry:
    def __init__(
        self,
        *,
        url: str,
        runner: CommandRunner | None = None,
        docker_bin: str = "docker",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        raw = (url or "").strip().rstrip("/")
        if raw.startswith("https://"):
            scheme, host = "https", raw.removeprefix("https://")
        elif raw.startswith("http://"):
            scheme, host = "http", raw.removeprefix("http://")
        else:
            # Mirror docker's own rule for scheme-less hosts: loopback registries are
            # plain HTTP (docker's insecure-by-default set), anything else is HTTPS —
            # otherwise our V2 API calls would target http:// while docker pushes to
            # https:// and retention would silently no-op.
            host = raw
            bare_host = host.split(":", 1)[0]
            loopback = bare_host in ("localhost", "[::1]") or bare_host.startswith("127.")
            scheme = "http" if loopback else "https"
        self.host = host.rstrip("/")
        self._api_base = f"{scheme}://{self.host}" if self.host else ""
        self._run = runner or _default_runner
        self.docker = docker_bin
        self._http = http_client

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    def ref_for(self, image: str) -> str:
        return f"{self.host}/{image}"

    async def _docker_ok(self, *args: str) -> bool:
        try:
            rc, _, _ = await self._run([self.docker, *args], None)
        except OSError:
            return False
        return rc == 0

    async def push(self, image: str) -> str | None:
        """Tag + push ``image`` to the registry; return the registry ref, or None.

        Best-effort by design: a down registry must never fail a deploy — the caller
        falls back to the local-only image name.
        """
        if not self.enabled:
            return None
        ref = self.ref_for(image)
        if not await self._docker_ok("tag", image, ref):
            logger.warning("registry tag failed for %s", image)
            return None
        if not await self._docker_ok("push", ref):
            logger.warning("registry push failed for %s", ref)
            return None
        # Untag the builder's bare name so the qualified ref is the image's only local
        # tag — otherwise retention's rmi of the qualified ref would only untag and
        # never reclaim disk. Nothing uses the bare name after this point (compose,
        # rollback and prune all use the recorded qualified ref).
        await self._docker_ok("rmi", image)
        logger.info("pushed %s to registry", ref)
        return ref

    async def image_exists(self, image: str) -> bool:
        return await self._docker_ok("image", "inspect", image)

    async def pull(self, ref: str) -> bool:
        return await self._docker_ok("pull", ref)

    async def remove_local(self, image: str) -> bool:
        return await self._docker_ok("rmi", image)

    async def delete_remote(self, ref: str) -> bool:
        """Untag ``ref`` in OUR registry (OCI distribution-spec 1.1 tag deletion).

        Deletes by TAG, never by digest: two commits can produce the identical image
        (build-cache hit → same manifest digest under two tags), and a digest DELETE
        would sever every sibling tag — including ones still inside the retention
        window. ``DELETE /v2/<repo>/manifests/<tag>`` (registry:3 / dist-spec 1.1)
        untags only this reference; untagged manifests+blobs are reclaimed by the
        registry's offline ``garbage-collect --delete-untagged``.

        Refuses refs that are local-only or belong to a different registry. Best-effort:
        any HTTP/transport error or an unsupported registry returns False. Requires
        REGISTRY_STORAGE_DELETE_ENABLED=true.
        """
        prefix = f"{self.host}/"
        if not self.enabled or not ref.startswith(prefix):
            return False
        repo, _, tag = ref.removeprefix(prefix).rpartition(":")
        if not repo or not tag:
            return False
        try:
            if self._http is not None:
                return await self._delete_tag(self._http, repo, tag)
            async with httpx.AsyncClient(timeout=10.0) as client:
                return await self._delete_tag(client, repo, tag)
        except httpx.HTTPError:
            logger.warning("registry manifest delete failed for %s", ref)
            return False

    async def _delete_tag(self, client: httpx.AsyncClient, repo: str, tag: str) -> bool:
        deleted = await client.delete(
            f"{self._api_base}/v2/{repo}/manifests/{tag}",
            headers={"Accept": _MANIFEST_ACCEPT},
        )
        return deleted.status_code in (200, 202)
