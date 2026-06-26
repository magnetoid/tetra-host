from fastapi import FastAPI

from app.plugins import PluginMeta
from app.modules.mail.routes import router


class MailPlugin:
    meta = PluginMeta("mail", "Mail", "Mailcow mailbox management", "Mail", "/mail")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
