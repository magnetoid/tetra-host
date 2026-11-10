from fastapi import FastAPI

from app.modules.auth.routes import router
from app.plugins import PluginMeta


class AuthPlugin:
    meta = PluginMeta("auth", "Auth", "Login and sessions", "Login", "/auth/login")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
