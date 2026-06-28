from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.databases.routes import router


class DatabasesPlugin:
    meta = PluginMeta("databases", "Databases", "Coolify database management", "🗄 Databases", "/databases")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
