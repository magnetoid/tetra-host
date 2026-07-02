from functools import lru_cache
from typing import Literal

from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cloud Industry Hosting"
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret: str = "change-me"
    base_url: str = "http://127.0.0.1:8088"
    database_url: str = "sqlite+aiosqlite:///./data/tetra_host.db"
    redis_url: str = ""
    allowed_hosts_raw: str = "127.0.0.1,localhost,testserver"
    theme: str = "cloud-industry"
    template_search_path: str = ""
    session_cookie_name: str = "tetra_host_session"
    session_max_age_seconds: int = 60 * 60 * 12
    session_https_only: bool = False
    session_same_site: Literal["lax", "strict", "none"] = "lax"
    force_https_redirect: bool = False
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    signup_rate_per_hour: int = 5
    max_pending_tenants: int = 100
    max_pending_tenants_per_ip: int = 3
    request_timeout_seconds: float = 20.0
    provider_cache_ttl_seconds: int = 30
    enable_provider_actions: bool = False

    coolify_url: str = ""
    coolify_token: str = ""
    mailcow_url: str = ""
    mailcow_api_key: str = ""
    cloudflare_api_token: str = ""
    # Hetzner Cloud (own-infra provisioning, ADR 0004 Phase 3). Empty token = disabled.
    hetzner_api_token: str = ""
    hetzner_server_type: str = "cx23"
    hetzner_image: str = "ubuntu-24.04"
    hetzner_location: str = "fsn1"
    # Cloudflare for SaaS (custom-hostname TLS, ADR 0009). Empty zone id = disabled.
    # When set, the token also needs the Zone > SSL and Certificates > Edit scope,
    # and cname_target is the proxied edge hostname customers point their CNAME at.
    cloudflare_saas_zone_id: str = ""
    cloudflare_saas_cname_target: str = ""

    # Umami web analytics (self-hosted v2). Empty url = analytics disabled (the
    # Metrics tab shows a "connect analytics" state). Self-hosted Umami has no API
    # keys, so we log in with username/password to mint a bearer token (cached).
    umami_url: str = ""
    umami_username: str = ""
    umami_password: str = ""

    # GlitchTip error tracking (Sentry-API-compatible). Empty url = errors disabled
    # (the Errors tab shows a "connect error tracking" state). Auth token + org slug.
    glitchtip_url: str = ""
    glitchtip_token: str = ""
    glitchtip_org: str = ""

    # Tetra Engine — independent Docker-native deployment (see docs/architecture/tetra-engine.md).
    docker_bin: str = "docker"
    nixpacks_bin: str = "nixpacks"
    app_catalog_url: str = ""
    apps_base_domain: str = ""
    # Shared external Docker network the Caddy edge is attached to. Empty = edge disabled
    # (apps still deploy, just not routed). See app/services/edge.py.
    edge_network: str = ""

    # Per-app resource allocation defaults used for plan coherence validation.
    default_app_cpu_millicores: int = 500
    default_app_mem_mb: int = 512
    default_app_disk_mb: int = 2048
    # Per-container PID cap (fork-bomb defense); applied with cpus/mem_limit hard caps.
    default_app_pids_limit: int = 256
    # Preview environments don't hold quota slots; they're capped per project instead.
    max_previews_per_project: int = 3

    deploy_notify_webhook_url: str = ""
    deploy_notify_webhook_bearer_token: str = ""
    deploy_notify_default_channel: Literal["none", "webhook", "sms"] = "none"
    deploy_notify_sms_to: str = ""
    deploy_notify_enabled_events_raw: str = "requested,success,failure"

    admin_bootstrap_email: str = "admin@cloud-industry.com"
    admin_bootstrap_password: str = ""
    admin_bootstrap_name: str = "Platform Admin"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("sqlite:///"):
            return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if value.startswith("postgresql://"): 
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("mailcow_url", "coolify_url", "base_url", "deploy_notify_webhook_url", mode="before")
    @classmethod
    def strip_provider_urls(cls, value: str) -> str:
        return value.rstrip("/") if isinstance(value, str) else value

    @field_validator("allowed_hosts_raw", "deploy_notify_enabled_events_raw")
    @classmethod
    def normalize_csv_strings(cls, value: str) -> str:
        return ",".join(part.strip() for part in value.split(",") if part.strip())

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.is_production and self.app_secret.startswith("change-me"):
            msg = "APP_SECRET must be changed before running in production."
            raise ValueError(msg)
        if self.session_same_site == "none" and not self.session_https_only:
            msg = "SESSION_SAME_SITE=none requires SESSION_HTTPS_ONLY=true."
            raise ValueError(msg)
        return self

    @computed_field
    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts_raw.split(",") if host.strip()]

    @computed_field
    @property
    def deploy_notify_enabled_events(self) -> list[str]:
        return [event.strip() for event in self.deploy_notify_enabled_events_raw.split(",") if event.strip()]

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field
    @property
    def provider_credentials_configured(self) -> bool:
        return any(
            [
                bool(self.coolify_url and self.coolify_token),
                bool(self.mailcow_url and self.mailcow_api_key),
                bool(self.cloudflare_api_token),
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
