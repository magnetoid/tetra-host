from fastapi import FastAPI

from app.modules.servers.routes import router
from app.plugins import PluginMeta


class ServersPlugin:
    meta = PluginMeta("servers", "Servers", "Coolify server management", "🖥 Servers", "/servers")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
