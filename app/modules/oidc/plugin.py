from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.oidc.routes import router


class OIDCPlugin:
    # No nav entry — OIDC is a machine + redirect surface (Mailcow ⇄ Tetra),
    # not a page. Endpoints stay dormant until `oidc_configured`.
    meta = PluginMeta("oidc", "OIDC", "OIDC Identity Provider for webmail SSO", "", "")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
