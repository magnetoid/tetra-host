from fastapi import FastAPI

from app.modules.dashboard.routes import router
from app.plugins import PluginMeta


class DashboardPlugin:
    meta = PluginMeta("dashboard", "Dashboard", "Overview and stats", "Dashboard", "/dashboard")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
