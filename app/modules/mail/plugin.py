from fastapi import FastAPI

from app.modules.mail.routes import router
from app.plugins import PluginMeta


class MailPlugin:
    meta = PluginMeta("mail", "Mail", "Mailcow mailbox management", "Mail", "/mail")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
