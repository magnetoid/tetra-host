from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cloud Industry Hosting"
    app_env: str = "development"
    app_secret: str = "change-me"
    base_url: str = "http://127.0.0.1:8088"
    database_url: str = "sqlite:///./data/tetra_host.db"
    coolify_url: str = ""
    coolify_token: str = ""
    mailcow_url: str = ""
    mailcow_api_key: str = ""
    cloudflare_api_token: str = ""
    theme: str = "cloud-industry"
    template_search_path: str = ""
    allowed_hosts_raw: str = "127.0.0.1,localhost,testserver"
    session_https_only: bool = False
    force_https_redirect: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = [h.strip() for h in self.allowed_hosts_raw.split(",") if h.strip()]
        if self.base_url:
            parsed = urlparse(self.base_url)
            if parsed.hostname and parsed.hostname not in hosts:
                hosts.append(parsed.hostname)
        return hosts


@lru_cache
def get_settings() -> Settings:
    return Settings()
