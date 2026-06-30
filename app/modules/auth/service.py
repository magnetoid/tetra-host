from datetime import UTC, datetime

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import AdminUser, Tenant
from app.models.admin import ROLE_OWNER, ROLE_PLATFORM_ADMIN
from app.models.tenant import TENANT_ACTIVE, TENANT_PENDING


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def normalize_slug(value: str) -> str:
        cleaned = "-".join(part for part in value.strip().lower().replace("_", "-").split("-") if part)
        return cleaned or "default"

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return pwd_context.verify(password, password_hash)

    async def get_admin_by_id(self, admin_id: str) -> AdminUser | None:
        result = await self.session.execute(
            select(AdminUser).options(selectinload(AdminUser.tenant)).where(AdminUser.id == admin_id)
        )
        return result.scalar_one_or_none()

    async def get_admin_by_email(self, email: str) -> AdminUser | None:
        result = await self.session.execute(
            select(AdminUser)
            .options(selectinload(AdminUser.tenant))
            .where(AdminUser.email == self.normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        result = await self.session.execute(select(Tenant).where(Tenant.slug == self.normalize_slug(slug)))
        return result.scalar_one_or_none()

    async def ensure_default_tenant(self) -> Tenant:
        tenant = await self.get_tenant_by_slug("default")
        if tenant is not None:
            return tenant

        tenant = Tenant(name="Default Tenant", slug="default", status=TENANT_ACTIVE, is_platform_scope=True)
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def authenticate(self, email: str, password: str) -> AdminUser | None:
        admin = await self.get_admin_by_email(email)
        if admin is None or not admin.is_active:
            return None
        if not self.verify_password(password, admin.password_hash):
            return None
        return admin

    async def touch_last_login(self, admin: AdminUser) -> None:
        admin.last_login_at = datetime.now(UTC)
        await self.session.flush()

    @staticmethod
    def validate_password(password: str) -> None:
        """Raise ValueError if password does not meet signup policy (>= 10 chars)."""
        if len(password) < 10:
            raise ValueError("Password must be at least 10 characters long.")

    async def _unique_slug(self, base: str) -> str:
        """Return a slug derived from base that is not already taken."""
        slug = self.normalize_slug(base)
        candidate = slug
        counter = 2
        while await self.get_tenant_by_slug(candidate) is not None:
            candidate = f"{slug}-{counter}"
            counter += 1
        return candidate

    async def signup(
        self,
        email: str,
        password: str,
        org_name: str,
        signup_ip: str | None = None,
    ) -> AdminUser | None:
        """Create a pending tenant + owner admin.

        Returns the created AdminUser on success, or None if the email already
        exists (caller must NOT mint a token in that case).

        Raises ValueError if the password fails the signup policy.
        """
        self.validate_password(password)

        normalized_email = self.normalize_email(email)
        existing = await self.get_admin_by_email(normalized_email)
        if existing is not None:
            # Duplicate email — return None (sentinel) without creating anything.
            return None

        # Resolve the default Free plan (may be None if no plans exist yet).
        from app.modules.plans.service import PlanService  # local import to avoid circular

        plan_service = PlanService(self.session)
        default_plan = await plan_service.get_default()
        plan_id = default_plan.id if default_plan is not None else None

        slug = await self._unique_slug(org_name)
        tenant = Tenant(
            name=org_name.strip() or slug,
            slug=slug,
            status=TENANT_PENDING,
            is_platform_scope=False,
            plan_id=plan_id,
            signup_ip=signup_ip,
        )
        self.session.add(tenant)
        await self.session.flush()

        admin = AdminUser(
            tenant_id=tenant.id,
            email=normalized_email,
            full_name=org_name.strip() or normalized_email,
            password_hash=self.hash_password(password),
            is_active=True,
            role=ROLE_OWNER,
        )
        self.session.add(admin)
        try:
            await self.session.flush()
        except IntegrityError:
            # Concurrent duplicate: roll back the whole unit-of-work (tenant + admin)
            # so no orphan tenant is left behind, then return the same None sentinel
            # as the pre-check duplicate path.
            await self.session.rollback()
            return None

        # Reload with relationships populated.
        return await self.get_admin_by_id(admin.id)

    async def ensure_bootstrap_admin(self, settings: Settings) -> AdminUser | None:
        if not settings.admin_bootstrap_password:
            return None

        tenant = await self.ensure_default_tenant()
        admin = await self.get_admin_by_email(settings.admin_bootstrap_email)
        if admin is not None:
            if not admin.tenant_id:
                admin.tenant_id = tenant.id
                await self.session.flush()
            return await self.get_admin_by_id(admin.id)

        admin = AdminUser(
            tenant_id=tenant.id,
            email=self.normalize_email(settings.admin_bootstrap_email),
            full_name=settings.admin_bootstrap_name,
            password_hash=self.hash_password(settings.admin_bootstrap_password),
            is_active=True,
            role=ROLE_PLATFORM_ADMIN,
        )
        self.session.add(admin)
        await self.session.flush()
        return await self.get_admin_by_id(admin.id)
