from fastapi import FastAPI

from app.plugins import PluginMeta


class PlansPlugin:
    meta = PluginMeta("plans", "Plans", "Subscription plan management", "", "")

    def register(self, app: FastAPI) -> None:
        # Plans has no HTML/HTMX panel routes — the console is its UI surface.
        # All JSON endpoints live in app/api/routes.py under /api/v1/plans.
        pass
