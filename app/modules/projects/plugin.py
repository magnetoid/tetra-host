from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.projects.routes import router


class ProjectsPlugin:
    meta = PluginMeta("projects", "Projects", "Coolify-backed project management", "Projects", "/projects")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
