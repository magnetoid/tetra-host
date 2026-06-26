from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.dashboard.routes import router


class DashboardPlugin:
    meta = PluginMeta("dashboard", "Dashboard", "Overview and stats", "Dashboard", "/dashboard")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
