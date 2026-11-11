from fastapi import FastAPI

from app.modules.maintenance.routes import router
from app.plugins import PluginMeta


class MaintenancePlugin:
    # platform_admin_only: the routes act on the shared orchestrator, so the nav entry
    # must not be advertised to tenant admins either (the routes enforce it regardless).
    meta = PluginMeta(
        "maintenance",
        "Maintenance",
        "Admin maintenance tools",
        "🔧 Maintenance",
        "/maintenance",
        platform_admin_only=True,
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
