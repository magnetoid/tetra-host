from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.public.routes import router


class PublicPlugin:
    meta = PluginMeta("public", "Public", "Landing pages", "Home", "/")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
