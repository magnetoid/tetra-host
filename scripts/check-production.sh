#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/tetra-host}
PYTHON=${PYTHON:-"$APP_DIR/.venv/bin/python"}

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "Missing $APP_DIR/.env"
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing Python interpreter at $PYTHON"
  exit 1
fi

(
  cd "$APP_DIR"
  set -a
  source ./.env
  set +a

  "$PYTHON" - <<'PY'
from urllib.parse import urlparse

from app.config import get_settings

settings = get_settings()
required = [
    ("APP_SECRET", settings.app_secret),
    ("DATABASE_URL", settings.database_url),
]

for key, value in required:
    if not value:
        raise SystemExit(f"Missing required setting: {key}")

if settings.is_production and settings.app_secret.startswith("change-me"):
    raise SystemExit("APP_SECRET still uses the insecure default.")

if settings.is_production:
    parsed_base_url = urlparse(settings.base_url)
    if parsed_base_url.scheme != "https":
        raise SystemExit("Production BASE_URL must use https.")
    if not parsed_base_url.hostname:
        raise SystemExit("Production BASE_URL must include a hostname.")
    if parsed_base_url.hostname not in settings.allowed_hosts:
        raise SystemExit("Production BASE_URL hostname must be present in ALLOWED_HOSTS_RAW.")
    if not settings.session_https_only:
        raise SystemExit("SESSION_HTTPS_ONLY must be true in production.")
    if not settings.force_https_redirect:
        raise SystemExit("FORCE_HTTPS_REDIRECT must be true in production.")

print("Configuration preflight passed.")
PY
)
