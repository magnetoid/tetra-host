from fastapi import FastAPI

from app.modules.databases.routes import router
from app.plugins import PluginMeta


class DatabasesPlugin:
    # API-only: the console (apps/web) renders databases; no Jinja nav entry.
    meta = PluginMeta(
        "databases",
        "Databases",
        "Managed Postgres, MySQL, MariaDB and Redis with scheduled backups",
        "",
        "",
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
