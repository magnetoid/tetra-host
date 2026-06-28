from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.servers.routes import router


class ServersPlugin:
    meta = PluginMeta("servers", "Servers", "Coolify server management", "🖥 Servers", "/servers")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
