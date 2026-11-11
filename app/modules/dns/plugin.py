from fastapi import FastAPI

from app.modules.dns.routes import router
from app.plugins import PluginMeta


class DnsPlugin:
    meta = PluginMeta("dns", "DNS", "Cloudflare DNS management", "DNS", "/dns")

    def register(self, app: FastAPI) -> None:
        app.include_router(router)
