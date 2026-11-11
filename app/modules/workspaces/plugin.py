from fastapi import FastAPI

from app.modules.workspaces.routes import router
from app.plugins import PluginMeta


class WorkspacesPlugin:
    # API-only: the console (apps/web) renders the hierarchy; no Jinja nav entry.
    meta = PluginMeta(
        "workspaces",
        "Workspaces",
        "Team → project → environment → app hierarchy",
        "",
        "",
    )

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
