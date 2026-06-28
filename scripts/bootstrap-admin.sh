#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/tetra-host}
PYTHON=${PYTHON:-"$APP_DIR/.venv/bin/python"}
ADMIN_EMAIL=${ADMIN_EMAIL:-${1:-}}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-${2:-}}
ADMIN_NAME=${ADMIN_NAME:-${3:-Platform Admin}}

if [[ -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
  echo "Usage: ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=secret [ADMIN_NAME='Platform Admin'] $0"
  exit 1
fi

(
  cd "$APP_DIR"
  set -a
  source ./.env
  export ADMIN_BOOTSTRAP_EMAIL="$ADMIN_EMAIL"
  export ADMIN_BOOTSTRAP_PASSWORD="$ADMIN_PASSWORD"
  export ADMIN_BOOTSTRAP_NAME="$ADMIN_NAME"
  set +a

  "$PYTHON" - <<'PY'
import asyncio

from app.config import get_settings
from app.db import init_db, session_scope
from app.modules.auth.service import AuthService


async def main() -> None:
    settings = get_settings()
    await init_db()
    async with session_scope() as session:
        service = AuthService(session)
        admin = await service.ensure_bootstrap_admin(settings)
        if admin is None:
            raise SystemExit("Bootstrap admin was not created.")
        print(f"Bootstrap admin ready: {admin.email}")


asyncio.run(main())
PY
)
