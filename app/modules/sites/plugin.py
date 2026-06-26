from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.sites.routes import router


class SitesPlugin:
    meta = PluginMeta("sites", "Sites", "Coolify-backed site management", "Sites", "/sites")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
