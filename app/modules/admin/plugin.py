from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.admin.routes import router


class AdminPlugin:
    meta = PluginMeta("admin", "Customers", "Tenant/customer administration", "Customers", "/admin")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
