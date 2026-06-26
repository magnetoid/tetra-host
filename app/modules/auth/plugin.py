from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.auth.routes import router


class AuthPlugin:
    meta = PluginMeta("auth", "Auth", "Login and sessions", "Login", "/auth/login")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
