from fastapi import FastAPI

from app.modules.public.routes import router
from app.plugins import PluginMeta


class PublicPlugin:
    meta = PluginMeta("public", "Public", "Landing pages", "Home", "/")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
