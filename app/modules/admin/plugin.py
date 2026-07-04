from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.admin.routes import router


class AdminPlugin:
    meta = PluginMeta(
        "admin", "Admin", "Platform administration", "Admin", "/admin",
        platform_admin_only=True,
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
