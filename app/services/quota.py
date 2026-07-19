"""QuotaService — per-tenant usage accounting and atomic app-slot reservation.

Atomicity design
----------------
The ``check_and_reserve`` method must be race-free: two concurrent installs for
the same tenant must not both pass the ``max_apps`` check.

On **PostgreSQL** we issue a *transaction-scoped advisory lock* keyed on the
tenant_id *before* reading the current count.  ``pg_advisory_xact_lock`` blocks
until the previous holder commits or rolls back, and the lock is automatically
released at end-of-transaction — no manual unlock required.

On **SQLite** (tests) there is no advisory-lock primitive.  We skip the call;
SQLite's per-connection write-locking provides best-effort serialisation for the
common single-process case.  The unit tests exercise the quota logic (not
concurrent contention) so this is sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Deployment, Plan, Tenant, TenantResource
from app.models.deployment import STATUS_BUILDING, STATUS_QUEUED
from app.models.tenant_resource import PROVIDER_DOCKER, RESOURCE_TYPE_APP

# The set of Deployment statuses that represent an in-flight (slot-consuming) build.
_INFLIGHT_STATUSES = (STATUS_QUEUED, STATUS_BUILDING)

# Fallback max_apps when neither the tenant's plan nor the "free" plan row exists.
# Must match the seeded Free plan's max_apps column default (Plan.max_apps default=1).
DEFAULT_FREE_MAX_APPS: int = 1


@dataclass
class Allocation:
    """Resource allocation to record alongside a new app reservation."""

    cpu_millicores: int
    mem_mb: int
    disk_mb: int


class QuotaExceeded(Exception):
    """Raised when a requested action would exceed the tenant's plan quota.

    Attributes
    ----------
    error:  Machine-readable error tag (always ``"quota_exceeded"``).
    reason: Which limit was hit — ``"apps"`` for the app-count check.
    limit:  The plan's cap.
    used:   How many slots are currently in use.
    """

    error: str = "quota_exceeded"

    def __init__(self, *, reason: str, limit: int, used: int) -> None:
        self.error = "quota_exceeded"
        self.reason = reason
        self.limit = limit
        self.used = used
        super().__init__(f"Quota exceeded: {reason} (used={used}, limit={limit})")


class QuotaService:
    """Per-tenant usage accounting and atomic reservation."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _count_apps(self) -> int:
        """Return current app-slot consumption, counting each distinct project once.

        TenantResource app rows are the authoritative set.  An in-flight Deployment
        is counted ONLY when its ``project`` is NOT already covered by a TenantResource
        reservation for this tenant, so a redeploy (reservation + active build for the
        same project) is never double-counted.
        """
        # Step 1: collect the set of project identifiers already reserved.
        reserved_ids_stmt = select(TenantResource.external_id).where(
            TenantResource.tenant_id == self._tenant_id,
            TenantResource.resource_type == RESOURCE_TYPE_APP,
        )
        reserved_rows = (await self._session.execute(reserved_ids_stmt)).scalars().all()
        reserved_ids: list[str] = list(reserved_rows)
        resource_count: int = len(reserved_ids)

        # Step 2: count in-flight Deployments whose project is NOT already reserved.
        deployment_stmt = select(func.count()).where(
            Deployment.tenant_id == self._tenant_id,
            Deployment.status.in_(_INFLIGHT_STATUSES),
        )
        if reserved_ids:
            deployment_stmt = deployment_stmt.where(
                Deployment.project.not_in(reserved_ids)
            )
        deployment_count: int = (await self._session.scalar(deployment_stmt)) or 0

        return resource_count + deployment_count

    async def _is_platform_scope(self) -> bool:
        """The platform-scope tenant is the operator (it runs the platform, not a
        billed customer), so it is exempt from per-plan resource quotas."""
        tenant = await self._session.get(Tenant, self._tenant_id)
        return bool(tenant and tenant.is_platform_scope)

    async def _resolve_plan(self) -> Plan | None:
        """Resolve the tenant's Plan, falling back to the seeded free plan."""
        tenant = await self._session.get(Tenant, self._tenant_id)
        plan: Plan | None = None
        if tenant and tenant.plan_id:
            plan = await self._session.get(Plan, tenant.plan_id)
        if plan is None:
            plan = await self._session.scalar(select(Plan).where(Plan.key == "free"))
        return plan

    async def _resolve_max_apps(self) -> int:
        """Resolve max_apps from the tenant's plan, falling back to the free plan."""
        plan = await self._resolve_plan()
        if plan is None:
            # Absolute last resort: use the module-level constant (matches the seeded Free plan).
            return DEFAULT_FREE_MAX_APPS
        return plan.max_apps

    async def plan_allocation(self) -> Allocation:
        """Per-app resource allocation derived from the tenant's plan.

        A plan's ``cpu_millicores``/``mem_mb``/``disk_mb`` columns are the
        tenant's *total* budget; each app gets a fair share (total ÷ max_apps),
        never below the global per-app defaults — so a larger plan tier grants
        larger containers while no app is ever starved below the baseline. These
        values are stored on the reservation row and read back at build time by
        the deploy engine (``_limits_for`` → ``apply_resource_limits``), so the
        plan tier now sizes the real cgroup caps, not just the app count.

        Disk has no cgroup analogue in the compose/Docker path, so ``disk_mb``
        remains advisory (recorded for accounting, not enforced).
        """
        cfg = get_settings()
        defaults = Allocation(
            cpu_millicores=cfg.default_app_cpu_millicores,
            mem_mb=cfg.default_app_mem_mb,
            disk_mb=cfg.default_app_disk_mb,
        )
        plan = await self._resolve_plan()
        if plan is None:
            return defaults
        share = max(plan.max_apps, 1)
        return Allocation(
            cpu_millicores=max(defaults.cpu_millicores, plan.cpu_millicores // share),
            mem_mb=max(defaults.mem_mb, plan.mem_mb // share),
            disk_mb=max(defaults.disk_mb, plan.disk_mb // share),
        )

    async def _acquire_tenant_lock(self) -> None:
        """Acquire a per-tenant advisory lock (Postgres only; no-op on SQLite).

        Must be called INSIDE the active transaction so the lock is released
        automatically on commit/rollback.
        """
        bind = self._session.get_bind()
        dialect_name: str = bind.dialect.name  # type: ignore[union-attr]
        if dialect_name == "postgresql":
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:t))"),
                {"t": self._tenant_id},
            )
        # SQLite: the connection write-lock provides best-effort serialisation.

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def usage(self) -> dict[str, int]:
        """Return current resource usage for this tenant.

        Returns
        -------
        dict with keys: ``apps``, ``cpu_millicores``, ``mem_mb``, ``disk_mb``.

        *apps* = count of TenantResource rows with resource_type=app
               + count of Deployment rows in {queued, building}.

        CPU/mem/disk are summed over the TenantResource app rows; NULL columns
        are coalesced in Python to the configured per-app defaults.
        """
        cfg = get_settings()

        # --- app count (TenantResource + in-flight Deployments) ---
        apps = await self._count_apps()

        # --- resource sums (only from committed TenantResource rows) ---
        rows_stmt = select(
            TenantResource.cpu_millicores,
            TenantResource.mem_mb,
            TenantResource.disk_mb,
        ).where(
            TenantResource.tenant_id == self._tenant_id,
            TenantResource.resource_type == RESOURCE_TYPE_APP,
        )
        rows = (await self._session.execute(rows_stmt)).all()

        total_cpu = sum((row.cpu_millicores or cfg.default_app_cpu_millicores) for row in rows)
        total_mem = sum((row.mem_mb or cfg.default_app_mem_mb) for row in rows)
        total_disk = sum((row.disk_mb or cfg.default_app_disk_mb) for row in rows)

        return {
            "apps": apps,
            "cpu_millicores": total_cpu,
            "mem_mb": total_mem,
            "disk_mb": total_disk,
        }

    async def check_and_reserve(
        self,
        project: str,
        allocation: Allocation,
        display_name: str,
    ) -> None:
        """Atomically check the app-count quota and, if OK, reserve a slot.

        Steps (all within the caller's session/transaction):
        1. Acquire per-tenant lock (Postgres advisory; no-op on SQLite).
        2. Re-read current app count under the lock.
        3. Resolve the tenant's plan max_apps.
        4. If ``current + 1 > max_apps`` → raise ``QuotaExceeded``.
        5. Else insert a TenantResource reservation row and flush it.

        CPU/mem/disk limits are NOT enforced — the allocation is recorded for
        bookkeeping only, per the task spec.

        Raises
        ------
        QuotaExceeded
            When adding one more app would exceed the plan's ``max_apps``.
        """
        # Step 1: acquire lock first, before reading.
        await self._acquire_tenant_lock()

        # Step 2: re-read count under the lock.
        current_apps = await self._count_apps()

        # Step 3+4: resolve plan limit and enforce — UNLESS this is the
        # platform-scope operator tenant, which runs the platform and is exempt.
        if not await self._is_platform_scope():
            max_apps = await self._resolve_max_apps()
            if current_apps + 1 > max_apps:
                raise QuotaExceeded(reason="apps", limit=max_apps, used=current_apps)

        # Step 5: insert reservation (flushed, not yet committed — caller's tx).
        reservation = TenantResource(
            tenant_id=self._tenant_id,
            provider=PROVIDER_DOCKER,
            resource_type=RESOURCE_TYPE_APP,
            external_id=project,
            display_name=display_name,
            cpu_millicores=allocation.cpu_millicores,
            mem_mb=allocation.mem_mb,
            disk_mb=allocation.disk_mb,
        )
        self._session.add(reservation)
        await self._session.flush()

    async def release(self, project: str) -> None:
        """Delete the TenantResource reservation for *project* (failed-build cleanup).

        Parameters
        ----------
        project:
            The ``external_id`` of the TenantResource row to delete.
        """
        stmt = delete(TenantResource).where(
            TenantResource.tenant_id == self._tenant_id,
            TenantResource.external_id == project,
            TenantResource.resource_type == RESOURCE_TYPE_APP,
        )
        await self._session.execute(stmt)
        await self._session.flush()
