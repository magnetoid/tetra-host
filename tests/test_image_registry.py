"""Registry-backed rollback durability: push built images, pull on rollback, retention.

The ImageRegistry is config-gated on REGISTRY_URL (empty = disabled, images stay
local-only). When enabled, every successful non-preview build is pushed and the
registry-qualified ref is recorded on the Deployment, so rollback can re-pull an
image that was evicted from the host. Retention keeps the newest N per project.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.db import session_scope
from app.models import AdminUser, Plan, Tenant, TenantResource
from app.models.deployment import STATUS_ERROR, STATUS_READY, Deployment
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP
from app.modules.auth.service import AuthService
from app.modules.deploys.service import DeploysService
from app.services.builder import BuildResult
from app.services.registry import ImageRegistry, is_registry_qualified


def make_runner(record, *, fail_on=None, missing_images=()):
    """Fake docker CLI: records argv; can fail one subcommand or report missing images."""

    async def runner(argv, cwd):
        record.append(argv)
        cmd = argv[1] if len(argv) > 1 else ""
        if fail_on and cmd == fail_on:
            return (1, "", f"{fail_on} failed")
        if cmd == "image" and "inspect" in argv:
            return (1, "", "no such image") if argv[-1] in missing_images else (0, "[]", "")
        return (0, "", "")

    return runner


def _http_404():
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))


# ── ImageRegistry unit tests (no DB, no docker) ─────────────────────────────


def test_disabled_registry_never_pushes():
    rec: list[list[str]] = []
    reg = ImageRegistry(url="", runner=make_runner(rec))
    assert not reg.enabled
    assert asyncio.run(reg.push("tetra-blog:abc")) is None
    assert rec == []


def test_push_tags_pushes_and_untags_bare_name():
    rec: list[list[str]] = []
    reg = ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec))
    ref = asyncio.run(reg.push("tetra-blog:abc"))
    assert ref == "127.0.0.1:5000/tetra-blog:abc"
    assert ["docker", "tag", "tetra-blog:abc", ref] in rec
    assert ["docker", "push", ref] in rec
    # The bare builder tag is untagged after a successful push, so retention's rmi of
    # the qualified ref actually reclaims disk instead of just untagging.
    assert ["docker", "rmi", "tetra-blog:abc"] in rec


def test_push_failure_keeps_bare_tag():
    rec: list[list[str]] = []
    reg = ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec, fail_on="push"))
    assert asyncio.run(reg.push("tetra-blog:abc")) is None
    assert ["docker", "rmi", "tetra-blog:abc"] not in rec  # local-only fallback survives


def test_push_is_best_effort_on_failure():
    for stage in ("tag", "push"):
        rec: list[list[str]] = []
        reg = ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec, fail_on=stage))
        assert asyncio.run(reg.push("tetra-blog:abc")) is None


def test_url_normalization_strips_scheme_and_slash():
    reg = ImageRegistry(url="http://registry.internal:5000/")
    assert reg.ref_for("tetra-a:1") == "registry.internal:5000/tetra-a:1"


def test_scheme_defaults_mirror_docker_insecure_rules():
    # Scheme-less non-loopback hosts are HTTPS (docker pushes over TLS there — the V2
    # API must match or retention silently no-ops); loopback stays plain HTTP.
    assert ImageRegistry(url="registry.internal:5000")._api_base == (
        "https://registry.internal:5000"
    )
    assert ImageRegistry(url="127.0.0.1:5000")._api_base == "http://127.0.0.1:5000"
    assert ImageRegistry(url="localhost:5000")._api_base == "http://localhost:5000"
    assert ImageRegistry(url="http://registry.internal:5000")._api_base == (
        "http://registry.internal:5000"
    )


def test_is_registry_qualified():
    # Builder-local names (tetra-<project>:<tag>) never contain a slash.
    assert is_registry_qualified("127.0.0.1:5000/tetra-blog:abc")
    assert not is_registry_qualified("tetra-blog:abc")


def test_image_exists_and_pull():
    rec: list[list[str]] = []
    reg = ImageRegistry(
        url="127.0.0.1:5000", runner=make_runner(rec, missing_images={"tetra-x:1"})
    )
    assert asyncio.run(reg.image_exists("tetra-y:1")) is True
    assert asyncio.run(reg.image_exists("tetra-x:1")) is False
    assert asyncio.run(reg.pull("127.0.0.1:5000/tetra-x:1")) is True
    assert ["docker", "pull", "127.0.0.1:5000/tetra-x:1"] in rec


def test_pull_failure_returns_false():
    rec: list[list[str]] = []
    reg = ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec, fail_on="pull"))
    assert asyncio.run(reg.pull("127.0.0.1:5000/tetra-x:1")) is False


def test_remove_local_issues_rmi():
    rec: list[list[str]] = []
    reg = ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec))
    assert asyncio.run(reg.remove_local("127.0.0.1:5000/tetra-blog:v1")) is True
    assert ["docker", "rmi", "127.0.0.1:5000/tetra-blog:v1"] in rec


# ── delete_remote (registry V2 API: HEAD manifest → digest → DELETE) ────────


def test_delete_remote_untags_by_tag_never_by_digest():
    """Deleting by DIGEST would sever every sibling tag sharing the manifest (two
    commits can build the identical image via cache hits) — deletion must target the
    tag reference only (OCI dist-spec 1.1 untag)."""
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "DELETE" and request.url.path == "/v2/tetra-blog/manifests/abc":
            return httpx.Response(202)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    reg = ImageRegistry(url="127.0.0.1:5000", http_client=client)
    assert asyncio.run(reg.delete_remote("127.0.0.1:5000/tetra-blog:abc")) is True
    assert calls == [("DELETE", "/v2/tetra-blog/manifests/abc")]
    assert not any("sha256" in path for _, path in calls)


def test_delete_remote_refuses_local_and_foreign_refs():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        return httpx.Response(202)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    reg = ImageRegistry(url="127.0.0.1:5000", http_client=client)
    assert asyncio.run(reg.delete_remote("tetra-blog:abc")) is False
    assert asyncio.run(reg.delete_remote("other.host:5000/tetra-blog:abc")) is False
    assert calls == []  # never talks to a registry it does not own


def test_delete_remote_false_when_manifest_missing():
    reg = ImageRegistry(url="127.0.0.1:5000", http_client=_http_404())
    assert asyncio.run(reg.delete_remote("127.0.0.1:5000/tetra-blog:gone")) is False


# ── Deploy pipeline integration (push, fallback, previews, retention) ───────


async def _seed_tenant(slug: str, email: str, *, project: str = "blog") -> str:
    async with session_scope() as session:
        auth = AuthService(session)
        plan = Plan(key=f"plan_{slug}", name="P", max_apps=10)
        session.add(plan)
        await session.flush()
        tenant = Tenant(name=slug, slug=slug, status="active", plan_id=plan.id)
        session.add(tenant)
        await session.flush()
        session.add(
            AdminUser(
                tenant_id=tenant.id, email=email, full_name="Owner",
                password_hash=auth.hash_password("reg-pass"), is_active=True,
            )
        )
        session.add(
            TenantResource(
                tenant_id=tenant.id, provider=PROVIDER_DOCKER,
                resource_type=RESOURCE_TYPE_APP, external_id=project, display_name=project,
            )
        )
        return tenant.id


async def _seed_queued(tenant_id: str, *, project: str = "blog") -> str:
    async with session_scope() as session:
        dep = Deployment(tenant_id=tenant_id, project=project, status="queued")
        session.add(dep)
        await session.flush()
        return dep.id


class FakeBuilder:
    def __init__(self, image: str = "tetra-blog:abc123"):
        self.image = image

    async def build_from_git(self, git_url, ref, *, project, on_line=None):
        return BuildResult(image=self.image, builder="dockerfile", commit="c" * 12, port=3000)


class FakeEngine:
    def __init__(self):
        self.composes: list[str] = []

    async def deploy_stack(self, project, compose, env=None):
        self.composes.append(compose)
        return {"ok": True}


def _service(registry: ImageRegistry, *, keep: int = 5) -> DeploysService:
    service = DeploysService(request=object())
    service.builder = FakeBuilder()
    service.engine = FakeEngine()
    service.registry = registry
    service.keep_images = keep
    return service


def test_deploy_pushes_and_records_registry_ref(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regp", "o@regp.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec), http_client=_http_404())
        )
        await service._run_deploy(
            dep_id, tenant_id, git_url="https://g/x", ref="main", project="blog", port=3000
        )
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.image, row.log, service.engine.composes

    status, image, log, composes = asyncio.run(go())
    assert status == STATUS_READY
    assert image == "127.0.0.1:5000/tetra-blog:abc123"
    assert "127.0.0.1:5000/tetra-blog:abc123" in composes[0]
    assert any(a[:2] == ["docker", "push"] for a in rec)


def test_deploy_survives_push_failure_with_local_image(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regf", "o@regf.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec, fail_on="push"))
        )
        await service._run_deploy(
            dep_id, tenant_id, git_url="https://g/x", ref="main", project="blog", port=3000
        )
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.image, row.log

    status, image, log = asyncio.run(go())
    assert status == STATUS_READY  # push failure must never fail the deploy
    assert image == "tetra-blog:abc123"
    assert "registry push failed" in log


def test_preview_deploy_skips_registry_push(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regv", "o@regv.test")
        dep_id = await _seed_queued(tenant_id, project="blog-git-feat")
        service = _service(ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec)))
        await service._run_deploy(
            dep_id, tenant_id, git_url="https://g/x", ref="feat",
            project="blog-git-feat", port=3000, env_project="blog",
        )
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.image

    status, image = asyncio.run(go())
    assert status == STATUS_READY
    assert image == "tetra-blog:abc123"  # local name — previews are ephemeral, never pushed
    assert not any(a[:2] == ["docker", "push"] for a in rec)


def test_prune_keeps_newest_n_and_protects_referenced_images(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regr", "o@regr.test")
        base = datetime.now(UTC)
        async with session_scope() as session:
            for i in range(6):
                session.add(
                    Deployment(
                        tenant_id=tenant_id, project="blog", status=STATUS_READY,
                        image=f"127.0.0.1:5000/tetra-blog:v{i}",
                        created_at=base + timedelta(minutes=i),
                    )
                )
            # A recent rollback row re-points at the OLDEST image → it must be protected.
            session.add(
                Deployment(
                    tenant_id=tenant_id, project="blog", status=STATUS_READY,
                    image="127.0.0.1:5000/tetra-blog:v0",
                    created_at=base + timedelta(minutes=10),
                )
            )
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec), http_client=_http_404()),
            keep=3,
        )
        await service._prune_old_images(tenant_id, "blog")

    asyncio.run(go())
    removed = {a[2] for a in rec if a[:2] == ["docker", "rmi"]}
    # Keep window (newest 3): v0-rollback, v5, v4. Stale: v3, v2, v1 — and v0 is protected.
    assert removed == {
        "127.0.0.1:5000/tetra-blog:v3",
        "127.0.0.1:5000/tetra-blog:v2",
        "127.0.0.1:5000/tetra-blog:v1",
    }


def test_prune_aborts_while_any_deployment_is_in_flight(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regx", "o@regx.test")
        base = datetime.now(UTC)
        async with session_scope() as session:
            for i in range(6):
                session.add(
                    Deployment(
                        tenant_id=tenant_id, project="blog", status=STATUS_READY,
                        image=f"127.0.0.1:5000/tetra-blog:v{i}",
                        created_at=base + timedelta(minutes=i),
                    )
                )
            # A rebuild in flight — it may not have recorded its image ref yet, so the
            # whole prune cycle must stand down rather than race it.
            session.add(
                Deployment(
                    tenant_id=tenant_id, project="blog", status="building",
                    created_at=base + timedelta(minutes=11),
                )
            )
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec), http_client=_http_404()),
            keep=3,
        )
        await service._prune_old_images(tenant_id, "blog")

    asyncio.run(go())
    assert not any(a[:2] == ["docker", "rmi"] for a in rec)


def test_prune_protects_cross_tenant_images(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regt", "o@regt.test")
        other_id = await _seed_tenant("regy", "o@regy.test")
        base = datetime.now(UTC)
        async with session_scope() as session:
            for i in range(6):
                session.add(
                    Deployment(
                        tenant_id=tenant_id, project="blog", status=STATUS_READY,
                        image=f"127.0.0.1:5000/tetra-blog:v{i}",
                        created_at=base + timedelta(minutes=i),
                    )
                )
            # v2 is referenced by ANOTHER tenant's deployment (project names are only
            # per-tenant unique, image names collide) → must be protected.
            session.add(
                Deployment(
                    tenant_id=other_id, project="blog", status=STATUS_READY,
                    image="127.0.0.1:5000/tetra-blog:v2",
                    created_at=base + timedelta(minutes=12),
                )
            )
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec), http_client=_http_404()),
            keep=3,
        )
        await service._prune_old_images(tenant_id, "blog")

    asyncio.run(go())
    removed = {a[2] for a in rec if a[:2] == ["docker", "rmi"]}
    # Window keeps v5, v4, v3; stale = v2, v1, v0 — but v2 is cross-tenant-referenced.
    assert removed == {"127.0.0.1:5000/tetra-blog:v1", "127.0.0.1:5000/tetra-blog:v0"}


def test_prune_window_counts_distinct_images_not_rows(client):
    """Rollbacks create duplicate READY rows re-pointing at old images; the window
    must still retain N DISTINCT rollbackable images."""
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regw", "o@regw.test")
        base = datetime.now(UTC)
        rows = [  # oldest → newest: v3, v4, v5 deployed; v3 rolled back to twice; v6 deployed
            "127.0.0.1:5000/tetra-blog:v3",
            "127.0.0.1:5000/tetra-blog:v4",
            "127.0.0.1:5000/tetra-blog:v5",
            "127.0.0.1:5000/tetra-blog:v3",
            "127.0.0.1:5000/tetra-blog:v3",
            "127.0.0.1:5000/tetra-blog:v6",
        ]
        async with session_scope() as session:
            for i, image in enumerate(rows):
                session.add(
                    Deployment(
                        tenant_id=tenant_id, project="blog", status=STATUS_READY,
                        image=image, created_at=base + timedelta(minutes=i),
                    )
                )
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec), http_client=_http_404()),
            keep=3,
        )
        await service._prune_old_images(tenant_id, "blog")

    asyncio.run(go())
    removed = {a[2] for a in rec if a[:2] == ["docker", "rmi"]}
    # Distinct by most-recent reference: v6, v3, v5, v4 → window keeps v6, v3, v5.
    # Row-based counting would have wrongly deleted v5 AND v4.
    assert removed == {"127.0.0.1:5000/tetra-blog:v4"}


def test_prune_cleans_failed_deployments_pushed_images(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regz", "o@regz.test")
        base = datetime.now(UTC)
        async with session_scope() as session:
            session.add(
                Deployment(
                    tenant_id=tenant_id, project="blog", status=STATUS_READY,
                    image="127.0.0.1:5000/tetra-blog:good1", created_at=base,
                )
            )
            # Pushed, then the container failed to start → dead weight in the registry.
            session.add(
                Deployment(
                    tenant_id=tenant_id, project="blog", status=STATUS_ERROR,
                    image="127.0.0.1:5000/tetra-blog:bad11",
                    created_at=base + timedelta(minutes=1),
                )
            )
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec), http_client=_http_404()),
            keep=3,
        )
        await service._prune_old_images(tenant_id, "blog")
        async with session_scope() as session:
            rows = list(
                await session.scalars(
                    select(Deployment).where(Deployment.tenant_id == tenant_id)
                )
            )
            return {r.status: r.image for r in rows}

    images_by_status = asyncio.run(go())
    removed = {a[2] for a in rec if a[:2] == ["docker", "rmi"]}
    assert removed == {"127.0.0.1:5000/tetra-blog:bad11"}
    assert images_by_status[STATUS_READY] == "127.0.0.1:5000/tetra-blog:good1"
    assert images_by_status[STATUS_ERROR] == ""  # cleared so later cycles skip it


def test_prune_disabled_registry_removes_nothing(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regd", "o@regd.test")
        base = datetime.now(UTC)
        async with session_scope() as session:
            for i in range(6):
                session.add(
                    Deployment(
                        tenant_id=tenant_id, project="blog", status=STATUS_READY,
                        image=f"tetra-blog:v{i}", created_at=base + timedelta(minutes=i),
                    )
                )
        service = _service(ImageRegistry(url="", runner=make_runner(rec)), keep=3)
        await service._prune_old_images(tenant_id, "blog")

    asyncio.run(go())
    # Without a registry, local images are the ONLY rollback copies — never prune them.
    assert not any(a[:2] == ["docker", "rmi"] for a in rec)


# ── Rollback: pull evicted images back from the registry ────────────────────


def test_rollback_pulls_missing_image_from_registry(client):
    ref = "127.0.0.1:5000/tetra-blog:old12"
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regb", "o@regb.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(
            ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec, missing_images={ref}))
        )
        await service._run_rollback(dep_id, tenant_id, project="blog", image=ref, port=3000)
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.log

    status, log = asyncio.run(go())
    assert status == STATUS_READY
    assert ["docker", "pull", ref] in rec
    assert "pulling from registry" in log


def test_rollback_present_image_is_not_pulled(client):
    ref = "127.0.0.1:5000/tetra-blog:cur"
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regc", "o@regc.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(ImageRegistry(url="127.0.0.1:5000", runner=make_runner(rec)))
        await service._run_rollback(dep_id, tenant_id, project="blog", image=ref, port=3000)
        async with session_scope() as session:
            return (await session.get(Deployment, dep_id)).status

    assert asyncio.run(go()) == STATUS_READY
    assert not any(a[:2] == ["docker", "pull"] for a in rec)


def test_rollback_fails_clearly_when_pull_fails(client):
    ref = "127.0.0.1:5000/tetra-blog:gone1"
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("rege", "o@rege.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(
            ImageRegistry(
                url="127.0.0.1:5000",
                runner=make_runner(rec, fail_on="pull", missing_images={ref}),
            )
        )
        await service._run_rollback(dep_id, tenant_id, project="blog", image=ref, port=3000)
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.error

    status, error = asyncio.run(go())
    assert status == STATUS_ERROR
    assert "retention window" in error


def test_rollback_fails_clearly_for_evicted_local_only_image(client):
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regl", "o@regl.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(
            ImageRegistry(
                url="127.0.0.1:5000",
                runner=make_runner(rec, missing_images={"tetra-blog:gone2"}),
            )
        )
        await service._run_rollback(
            dep_id, tenant_id, project="blog", image="tetra-blog:gone2", port=3000
        )
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.error

    status, error = asyncio.run(go())
    assert status == STATUS_ERROR
    assert "predates the registry" in error
    assert not any(a[:2] == ["docker", "pull"] for a in rec)  # nothing to pull from


def test_rollback_message_honest_when_no_registry_configured(client):
    """Without a registry, 'predates the registry' would be nonsense — the message
    must say none is configured."""
    rec: list[list[str]] = []

    async def go():
        tenant_id = await _seed_tenant("regn", "o@regn.test")
        dep_id = await _seed_queued(tenant_id)
        service = _service(
            ImageRegistry(url="", runner=make_runner(rec, missing_images={"tetra-blog:gone3"}))
        )
        await service._run_rollback(
            dep_id, tenant_id, project="blog", image="tetra-blog:gone3", port=3000
        )
        async with session_scope() as session:
            row = await session.get(Deployment, dep_id)
            return row.status, row.error

    status, error = asyncio.run(go())
    assert status == STATUS_ERROR
    assert "no registry is configured" in error
