from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Tenant, User
from app.security import SessionUser, hash_password


@dataclass(frozen=True)
class TenantSummary:
    id: int
    name: str
    slug: str
    plan: str
    sites: int
    users: int


def ensure_bootstrap_data(
    admin_email: str = "admin@cloud-industry.com",
    admin_password: str = "change-me-now",
    tenant_name: str = "Cloud Industry",
    tenant_slug: str = "cloud-industry",
) -> None:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            tenant = Tenant(name=tenant_name, slug=tenant_slug, plan="Admin")
            db.add(tenant)
            db.flush()

        existing_user = db.scalar(select(User).where(User.email == admin_email))
        if existing_user is None:
            db.add(
                User(
                    tenant_id=tenant.id,
                    email=admin_email,
                    password_hash=hash_password(admin_password),
                    full_name="Cloud Industry Admin",
                    role="owner",
                )
            )

        existing_project = db.scalar(select(Project).where(Project.external_id == "bootstrap-cloud-industry"))
        if existing_project is None:
            db.add(
                Project(
                    tenant_id=tenant.id,
                    external_id="bootstrap-cloud-industry",
                    name="Cloud Industry Panel",
                    primary_domain="panel.cloud-industry.com",
                    environment="Production",
                    status="active",
                    repository="magnetoid/tetra-host",
                )
            )
        db.commit()


def authenticate_user(email: str) -> User | None:
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.email == email.lower().strip()))


def get_tenant_summaries() -> list[TenantSummary]:
    with SessionLocal() as db:
        tenants = db.scalars(select(Tenant).order_by(Tenant.name.asc())).all()
        projects = db.scalars(select(Project)).all()
        users = db.scalars(select(User)).all()

    project_counts: dict[int, int] = {}
    user_counts: dict[int, int] = {}
    for project in projects:
        project_counts[project.tenant_id] = project_counts.get(project.tenant_id, 0) + 1
    for user in users:
        user_counts[user.tenant_id] = user_counts.get(user.tenant_id, 0) + 1

    return [
        TenantSummary(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            plan=tenant.plan,
            sites=project_counts.get(tenant.id, 0),
            users=user_counts.get(tenant.id, 0),
        )
        for tenant in tenants
    ]


def sync_projects_for_tenant(tenant_slug: str, applications: Iterable) -> None:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            return
        existing = {
            project.external_id: project
            for project in db.scalars(select(Project).where(Project.tenant_id == tenant.id)).all()
        }
        seen: set[str] = set()
        for app in applications:
            external_id = str(app.id)
            seen.add(external_id)
            project = existing.get(external_id)
            if project is None:
                project = Project(tenant_id=tenant.id, external_id=external_id, name=app.name)
                db.add(project)
            project.name = app.name
            project.primary_domain = app.primary_domain
            project.environment = app.environment
            project.status = app.status
            project.repository = app.repository
        db.commit()


def current_user_from_session(session_user: SessionUser | None) -> User | None:
    if session_user is None:
        return None
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.id == session_user.user_id))
