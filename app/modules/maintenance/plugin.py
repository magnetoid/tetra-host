from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.maintenance.routes import router


class MaintenancePlugin:
    meta = PluginMeta("maintenance", "Maintenance", "Admin maintenance tools", "🔧 Maintenance", "/maintenance")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
