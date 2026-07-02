from fastapi import FastAPI

from app.plugins import PluginMeta


class DomainsPlugin:
    # No nav entry (empty nav_href): domains surface per-app in the console, and the
    # JSON endpoints live on the central /api/v1 contract.
    meta = PluginMeta("domains", "Domains", "Custom domains for native apps", "", "")

    def register(self, app: FastAPI) -> None:
        # API routes are part of app/api/routes.py (central /api/v1 contract).
        return None
