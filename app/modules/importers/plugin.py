from fastapi import FastAPI

from app.modules.importers.routes import router
from app.plugins import PluginMeta


class ImportersPlugin:
    # API-only for now (CLI: `tetra import ...`); no panel nav entry.
    meta = PluginMeta(
        "importers",
        "Importers",
        "Move existing Coolify apps onto the Tetra Engine",
        "",
        "",
        platform_admin_only=True,
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
