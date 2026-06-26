from functools import lru_cache
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
