from fastapi import FastAPI

from app.modules.account.routes import router
from app.plugins import PluginMeta


class AccountPlugin:
    # Empty nav_href: the account page is reached from the header dropdown, not the
    # sidebar nav.
    meta = PluginMeta("account", "Account", "Your profile and settings", "", "")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
