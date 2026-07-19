from functools import lru_cache
from typing import Literal

from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cloud Industry Hosting"
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret: str = "change-me"
    log_format: Literal["text", "json"] = "text"
    base_url: str = "http://127.0.0.1:8088"
    database_url: str = "sqlite+aiosqlite:///./data/tetra_host.db"
    redis_url: str = ""
    allowed_hosts_raw: str = "127.0.0.1,localhost,testserver"
    # Origin-based CSRF backstop for the browser (session-cookie) surface. On by
    # default; the /api, /graphql, and OIDC-token surfaces are always exempt.
    csrf_protect: bool = True
    theme: str = "cloud-industry"
    template_search_path: str = ""
    session_cookie_name: str = "tetra_host_session"
    session_max_age_seconds: int = 60 * 60 * 12
    session_https_only: bool = False
    session_same_site: Literal["lax", "strict", "none"] = "lax"
    force_https_redirect: bool = False
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    # Per-personal-API-token request cap (sliding 60s window). 0 = disabled. Only
    # applies to `tetra_…` bearer tokens — the console's session auth is never
    # rate-limited, so SSR page loads are unaffected.
    api_rate_limit_per_minute: int = 300
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
    # Verify Mailcow's TLS cert. Set false when Mailcow runs on a self-signed
    # loopback endpoint (e.g. co-located on the box at https://127.0.0.1:8480).
    mailcow_verify_tls: bool = True
    cloudflare_api_token: str = ""
    # Cloudflare R2 object-storage reselling. Empty account id = R2 disabled (the Storage
    # surface shows a "not configured" state). The api_token above must additionally carry
    # "Workers R2 Storage Write"; to mint per-bucket S3 credentials the token also needs
    # "API Tokens Write" and `cloudflare_r2_permission_group_id` must be the id of the
    # "Workers R2 Storage Bucket Item Write" permission group (GET /accounts/{id}/tokens/
    # permission_groups). jurisdiction ("default"|"eu"|"fedramp") is fixed at bucket creation.
    cloudflare_account_id: str = ""
    cloudflare_r2_permission_group_id: str = ""
    cloudflare_r2_jurisdiction: str = "default"
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
    # OpenRouter reselling (AI models). Two credential modes, checked in order:
    #  1. PROVISIONING key (openrouter.ai/settings/management-keys) — mints/manages a
    #     per-tenant runtime key each with its own OpenRouter-enforced spend cap. Preferred.
    #  2. RUNTIME key (sk-or-v1-…) — a single shared key that powers a SHARED GATEWAY: tenants
    #     call Tetra's /api/v1/ai/chat with their Tetra token, Tetra forwards to OpenRouter on
    #     this one key and meters each tenant's usage into the charge ledger. Per-tenant hard
    #     caps arrive with the credit wallet; until then the key's own OpenRouter limit is the
    #     global safety cap. Used only when no provisioning key is set.
    openrouter_provisioning_key: str = ""
    openrouter_runtime_key: str = ""
    # Reseller safety switch: while FALSE (default), any Cloudflare activation that would
    # incur a real charge (paid zone plan or a usage-billed toggle like Argo) is refused —
    # no billable calls reach Cloudflare. Flip to True only once the billing/markup model
    # is live. Account-level add-ons (recorded pending, no charge) are unaffected.
    reseller_cloudflare_billing_enabled: bool = False
    # Reseller billing (slice 1): platform default markup applied to an offering's wholesale
    # cost when no per-offering PricingRule exists. Percent, e.g. 30.0 = +30%.
    reseller_default_markup_percent: float = 30.0

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

    # AI-assisted build-failure diagnosis ("tetra ai explain", ADR 0013). Empty key =
    # the deterministic heuristic analyzer only (no LLM). When set, failed-build logs are
    # sent to the Anthropic Messages API for a richer diagnosis (best-effort, falls back
    # to the heuristic on any error). See app/services/build_diagnostics.py.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # Tetra Engine — independent Docker-native deployment (see docs/architecture/tetra-engine.md).
    docker_bin: str = "docker"
    nixpacks_bin: str = "nixpacks"
    # In-process cron scheduler for tenant scheduled jobs (HTTP triggers). Runs one asyncio
    # task in the app lifespan. Disable in tests / multi-instance deploys.
    scheduler_enabled: bool = True
    # Per-minute uptime probing of tenant monitors (rides the same scheduler tick).
    # Fires app.down/app.up notifications on a state transition.
    uptime_checks_enabled: bool = True
    # GitHub token for cloning PRIVATE repos in the deploy builder. Empty = only public repos
    # clone (private ones fail with "could not read Username"). A PAT (classic or fine-grained)
    # with repo:read; injected as x-access-token into the clone URL and scrubbed from all logs.
    github_token: str = ""
    app_catalog_url: str = ""
    apps_base_domain: str = ""
    # Shared external Docker network the Caddy edge is attached to. Empty = edge disabled
    # (apps still deploy, just not routed). See app/services/edge.py.
    edge_network: str = ""
    # Mail platform (Phase 2, ADR 0015). MAIL_HOSTNAME is the MX target (the dedicated
    # Mailcow host FQDN) — empty skips the MX record in DNS automation. SPF/DMARC
    # contents are configurable so an ESP include can be added. A non-zero
    # MAIL_DEFAULT_RELAYHOST_ID auto-assigns that mailcow relayhost (ESP sender-
    # dependent transport) to every newly created mail domain.
    mail_hostname: str = ""
    mail_spf_record: str = "v=spf1 mx ~all"
    mail_dmarc_record: str = "v=DMARC1; p=quarantine"
    mail_default_relayhost_id: int = 0

    # ── OIDC Identity Provider (passwordless webmail, ADR pending) ───────────
    # Tetra acts as an OIDC IdP so Mailcow can drop an already-authenticated
    # tenant straight into SOGo webmail (Mailcow "Proxy Auth"). Dormant unless a
    # signing key + client credentials are set. `oidc_issuer` is Tetra's public
    # base URL (e.g. https://panel.cloud-industry.com); the private key is a
    # PEM RSA key (generate with scripts/gen-oidc-key.sh). `oidc_client_id` /
    # `oidc_client_secret` are the single client (Mailcow). `oidc_redirect_uris`
    # is a comma-separated allowlist of Mailcow callback URLs. `oidc_webmail_url`
    # is where the "Open webmail" button sends the browser to start the flow.
    oidc_issuer: str = ""
    oidc_private_key_pem: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uris_raw: str = ""
    oidc_webmail_url: str = ""

    # Image registry for rollback durability (ADR 0014). Empty = disabled: built images
    # stay local-only and rollback depends on them not being pruned. Set a host:port
    # (e.g. 127.0.0.1:5000, see scripts/install-registry.sh) to push every successful
    # non-preview build and record the registry-qualified ref so rollback can re-pull
    # evicted images. keep_images bounds the per-project rollback window; older images
    # are deleted locally and in the registry.
    registry_url: str = ""
    registry_keep_images: int = 5

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

    @field_validator("mail_default_relayhost_id", "registry_keep_images", mode="before")
    @classmethod
    def blank_int_means_default(cls, value: object) -> object:
        # Operators commonly leave optional int vars blank in .env / systemd
        # EnvironmentFile; a bare "" must mean "unset", not a boot-time crash.
        if value in ("", None):
            return 0
        return value

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
    def oidc_redirect_uris(self) -> list[str]:
        return [uri.strip() for uri in self.oidc_redirect_uris_raw.split(",") if uri.strip()]

    @computed_field
    @property
    def oidc_configured(self) -> bool:
        """OIDC IdP is live only when a signing key + client + issuer are set."""
        return bool(
            self.oidc_issuer
            and self.oidc_private_key_pem
            and self.oidc_client_id
            and self.oidc_client_secret
            and self.oidc_redirect_uris
        )

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
