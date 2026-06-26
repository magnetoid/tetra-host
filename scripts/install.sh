#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/tetra-host}
USER_NAME=${USER_NAME:-tetrahost}
PYTHON=${PYTHON:-python3}

if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$USER_NAME"
fi
mkdir -p "$APP_DIR" "$APP_DIR/data"
rsync -a --delete ./ "$APP_DIR/"
cd "$APP_DIR"
$PYTHON -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp -n .env.example .env || true
chown -R "$USER_NAME:$USER_NAME" "$APP_DIR"
cp systemd/tetra-host.service /etc/systemd/system/tetra-host.service
systemctl daemon-reload
systemctl enable tetra-host
systemctl restart tetra-host
systemctl status tetra-host --no-pager
