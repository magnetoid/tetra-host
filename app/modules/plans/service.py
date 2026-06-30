"""PlanService — business logic for subscription plan management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Plan


class PlanService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_plans(self, *, include_archived: bool = False) -> list[Plan]:
        stmt = select(Plan)
        if not include_archived:
            stmt = stmt.where(Plan.is_archived.is_(False))
        stmt = stmt.order_by(Plan.sort_order, Plan.name)
        return list((await self._session.scalars(stmt)).all())

    async def get_by_id(self, plan_id: str) -> Plan | None:
        return await self._session.get(Plan, plan_id)

    async def get_default(self) -> Plan | None:
        """Return the plan keyed 'free' (the default subscription tier)."""
        return await self._session.scalar(select(Plan).where(Plan.key == "free"))

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def _validate_coherence(self, max_apps: int, cpu_millicores: int, mem_mb: int) -> None:
        """Raise ValueError if per-app allocation would exceed plan totals."""
        settings = get_settings()
        required_cpu = max_apps * settings.default_app_cpu_millicores
        required_mem = max_apps * settings.default_app_mem_mb
        if required_cpu > cpu_millicores:
            msg = (
                f"Plan incoherent: max_apps={max_apps} × "
                f"default_app_cpu_millicores={settings.default_app_cpu_millicores} "
                f"({required_cpu}) exceeds cpu_millicores={cpu_millicores}."
            )
            raise ValueError(msg)
        if required_mem > mem_mb:
            msg = (
                f"Plan incoherent: max_apps={max_apps} × "
                f"default_app_mem_mb={settings.default_app_mem_mb} "
                f"({required_mem}) exceeds mem_mb={mem_mb}."
            )
            raise ValueError(msg)

    async def create(
        self,
        *,
        key: str,
        name: str,
        description: str = "",
        price_cents: int = 0,
        currency: str = "usd",
        max_apps: int,
        max_domains: int,
        cpu_millicores: int,
        mem_mb: int,
        disk_mb: int,
        sort_order: int = 0,
    ) -> Plan:
        self._validate_coherence(max_apps, cpu_millicores, mem_mb)
        plan = Plan(
            key=key.strip().lower(),
            name=name.strip(),
            description=description.strip(),
            price_cents=price_cents,
            currency=currency.strip().lower(),
            max_apps=max_apps,
            max_domains=max_domains,
            cpu_millicores=cpu_millicores,
            mem_mb=mem_mb,
            disk_mb=disk_mb,
            sort_order=sort_order,
        )
        self._session.add(plan)
        await self._session.flush()
        await self._session.refresh(plan)
        return plan

    async def update(self, plan_id: str, **fields: object) -> Plan | None:
        plan = await self.get_by_id(plan_id)
        if plan is None:
            return None

        # Apply only the fields provided (partial update).
        for field, value in fields.items():
            if value is not None:
                setattr(plan, field, value)

        # Re-validate coherence with the (possibly updated) values.
        self._validate_coherence(plan.max_apps, plan.cpu_millicores, plan.mem_mb)

        await self._session.flush()
        await self._session.refresh(plan)
        return plan

    async def archive(self, plan_id: str) -> Plan | None:
        plan = await self.get_by_id(plan_id)
        if plan is None:
            return None
        plan.is_archived = True
        await self._session.flush()
        await self._session.refresh(plan)
        return plan
