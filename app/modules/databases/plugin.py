from fastapi import FastAPI

from app.modules.databases.routes import router
from app.plugins import PluginMeta


class DatabasesPlugin:
    meta = PluginMeta("databases", "Databases", "Coolify database management", "🗄 Databases", "/databases")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
