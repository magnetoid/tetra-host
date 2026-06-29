from datetime import UTC, datetime

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import AdminUser, Tenant
from app.models.tenant import TENANT_ACTIVE


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
        )
        self.session.add(admin)
        await self.session.flush()
        return await self.get_admin_by_id(admin.id)
