#!/usr/bin/env bash
#
# install.sh — clean-server installer for Tetra Host (Cloud Industry PaaS panel).
#
# Provisions the FastAPI panel end-to-end on a fresh Ubuntu/Debian server, with
# optional nginx + Let's Encrypt TLS, the Next.js console, and the Docker deploy
# engine. Idempotent: safe to re-run to upgrade or add components.
#
# Quick start (fresh Ubuntu 22.04/24.04, as root):
#   curl -fsSL https://raw.githubusercontent.com/magnetoid/tetra-host/main/scripts/install.sh | sudo bash -s -- \
#     --domain panel.example.com --admin-email you@example.com
#
# Or from a local checkout:
#   sudo bash scripts/install.sh --domain panel.example.com --admin-email you@example.com
#
# Flags (all optional — with none, installs a local dev panel on 127.0.0.1:8088):
#   --domain <fqdn>           Serve the panel at https://<fqdn> via nginx + certbot (implies production).
#   --console-domain <fqdn>   Serve the Next.js console at https://<fqdn> (implies --with-console).
#   --with-console            Build the Next.js console, run it as the tetra-console service (Node 22).
#   --with-docker             Install Docker + Compose v2 and enable the Tetra deploy engine.
#   --apps-domain <fqdn>      Base domain for deployed apps (e.g. apps.example.com); pairs with --with-docker.
#   --admin-email <email>     Seed a bootstrap admin (password from --admin-password or auto-generated).
#   --admin-password <pw>     Bootstrap admin password (default: random, printed at the end).
#   --branch <name>           Git branch to install when cloning (default: main).
#   --no-start                Install everything but don't start services.
#   -h, --help                Show this help.
#
# Env overrides: APP_DIR (default /opt/tetra-host), USER_NAME (tetrahost),
#                REPO (default https://github.com/magnetoid/tetra-host), CERTBOT_EMAIL.
#
set -euo pipefail

# ── Config / defaults ─────────────────────────────────────────────────────
APP_DIR="${APP_DIR:-/opt/tetra-host}"
USER_NAME="${USER_NAME:-tetrahost}"
REPO="${REPO:-https://github.com/magnetoid/tetra-host}"
BRANCH="main"

DOMAIN=""
CONSOLE_DOMAIN=""
WITH_CONSOLE=0
WITH_DOCKER=0
APPS_DOMAIN=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
START=1

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

# ── Parse args ────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)          DOMAIN="${2:?}"; shift 2 ;;
    --console-domain)  CONSOLE_DOMAIN="${2:?}"; WITH_CONSOLE=1; shift 2 ;;
    --with-console)    WITH_CONSOLE=1; shift ;;
    --with-docker)     WITH_DOCKER=1; shift ;;
    --apps-domain)     APPS_DOMAIN="${2:?}"; shift 2 ;;
    --admin-email)     ADMIN_EMAIL="${2:?}"; shift 2 ;;
    --admin-password)  ADMIN_PASSWORD="${2:?}"; shift 2 ;;
    --branch)          BRANCH="${2:?}"; shift 2 ;;
    --no-start)        START=0; shift ;;
    -h|--help)         usage ;;
    *) die "Unknown option: $1 (try --help)" ;;
  esac
done

PRODUCTION=0
[[ -n "$DOMAIN" ]] && PRODUCTION=1

# ── Preconditions ─────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root (sudo bash scripts/install.sh ...)."
command -v apt-get >/dev/null || die "This installer targets Ubuntu/Debian (apt-get not found)."
[[ -z "$DOMAIN" || "$DOMAIN" == *.* ]] || die "--domain must be a FQDN like panel.example.com"

# ── System dependencies ───────────────────────────────────────────────────
log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 python3-venv python3-dev build-essential \
  git curl rsync ca-certificates openssl sqlite3
[[ $PRODUCTION -eq 1 || -n "$CONSOLE_DOMAIN" ]] && apt-get install -y -qq nginx

# ── Fetch source (rsync from a checkout, else clone) ──────────────────────
SCRIPT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
id "$USER_NAME" >/dev/null 2>&1 || { log "Creating system user $USER_NAME"; useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$USER_NAME"; }
mkdir -p "$APP_DIR" "$APP_DIR/data" "$APP_DIR/logs"

if [[ -f "$SCRIPT_ROOT/requirements.txt" && "$SCRIPT_ROOT" != "$APP_DIR" ]]; then
  log "Syncing source from checkout: $SCRIPT_ROOT -> $APP_DIR"
  rsync -a --delete \
    --exclude ".env" --exclude ".venv" --exclude "data" --exclude "logs" \
    --exclude ".git" --exclude "node_modules" --exclude ".next" \
    "$SCRIPT_ROOT"/ "$APP_DIR"/
elif [[ -d "$APP_DIR/.git" ]]; then
  log "Updating existing checkout at $APP_DIR (branch $BRANCH)"
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  log "Cloning $REPO (branch $BRANCH) -> $APP_DIR"
  git clone --branch "$BRANCH" --depth 1 "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

# ── Python venv + deps ────────────────────────────────────────────────────
log "Creating Python virtualenv and installing dependencies"
python3 -m venv .venv
./.venv/bin/pip install --upgrade -q pip
./.venv/bin/pip install -q -r requirements.txt

# ── .env (create + configure; never clobber an existing one) ──────────────
set_env() {
  local key="$1" val="$2" file="$APP_DIR/.env"
  val=${val//\\/\\\\}; val=${val//|/\\|}
  if grep -qE "^${key}=" "$file"; then
    sed -i -E "s|^${key}=.*|${key}=${val}|" "$file"
  else
    printf '%s=%s\n' "$key" "$val" >> "$file"
  fi
}

if [[ ! -f "$APP_DIR/.env" ]]; then
  log "Creating .env from .env.example"
  cp .env.example .env
  set_env APP_SECRET "$(openssl rand -hex 32)"
  if [[ $PRODUCTION -eq 1 ]]; then
    set_env APP_ENV production
    set_env BASE_URL "https://${DOMAIN}"
    set_env ALLOWED_HOSTS_RAW "${DOMAIN},127.0.0.1,localhost,testserver"
    set_env SESSION_HTTPS_ONLY true
    set_env FORCE_HTTPS_REDIRECT true
  fi
  if [[ $WITH_DOCKER -eq 1 ]]; then
    set_env ENABLE_PROVIDER_ACTIONS true
    [[ -n "$APPS_DOMAIN" ]] && set_env APPS_BASE_DOMAIN "$APPS_DOMAIN"
  fi
else
  warn ".env already exists — leaving it untouched (config not modified)."
fi

# ── Permissions + systemd unit ────────────────────────────────────────────
chown -R "$USER_NAME:$USER_NAME" "$APP_DIR"
chmod 0640 "$APP_DIR/.env" || true
chmod +x scripts/check-production.sh scripts/bootstrap-admin.sh

log "Installing systemd unit tetra-host"
install -m 0644 systemd/tetra-host.service /etc/systemd/system/tetra-host.service
systemctl daemon-reload
systemctl enable tetra-host >/dev/null 2>&1 || true

log "Running configuration preflight"
sudo -u "$USER_NAME" APP_DIR="$APP_DIR" "$APP_DIR/scripts/check-production.sh"

# ── Bootstrap admin ───────────────────────────────────────────────────────
if [[ -n "$ADMIN_EMAIL" ]]; then
  [[ -n "$ADMIN_PASSWORD" ]] || { ADMIN_PASSWORD="$(openssl rand -base64 18)"; GENERATED_PW=1; }
  log "Seeding bootstrap admin: $ADMIN_EMAIL"
  sudo -u "$USER_NAME" APP_DIR="$APP_DIR" \
    ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    "$APP_DIR/scripts/bootstrap-admin.sh"
fi

# ── Optional: Next.js console (Node 22 + build + service) ─────────────────
if [[ $WITH_CONSOLE -eq 1 ]]; then
  log "Installing Node.js 22 for the console"
  node_major="$(node -v 2>/dev/null | sed -n 's/^v\([0-9]\{1,\}\).*/\1/p')"
  if [[ -z "$node_major" || "$node_major" -lt 22 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
    apt-get install -y -qq nodejs
  fi
  corepack enable
  corepack prepare pnpm@9 --activate

  log "Building the console (apps/web) — this can take a few minutes"
  chown -R "$USER_NAME:$USER_NAME" "$APP_DIR/apps"
  sudo -u "$USER_NAME" bash -lc "cd '$APP_DIR/apps/web' && pnpm install --frozen-lockfile && pnpm build"

  log "Installing systemd unit tetra-console"
  install -m 0644 systemd/tetra-console.service /etc/systemd/system/tetra-console.service
  systemctl daemon-reload
  systemctl enable tetra-console >/dev/null 2>&1 || true
fi

# ── Optional: Docker deploy engine ────────────────────────────────────────
if [[ $WITH_DOCKER -eq 1 ]]; then
  if ! command -v docker >/dev/null; then
    log "Installing Docker Engine + Compose v2"
    curl -fsSL https://get.docker.com | sh >/dev/null
  fi
  log "Granting $USER_NAME access to the Docker daemon"
  usermod -aG docker "$USER_NAME"
  systemctl enable --now docker >/dev/null 2>&1 || true
fi

# ── Optional: nginx vhosts + Let's Encrypt TLS ────────────────────────────
write_vhost() {
  local domain="$1" port="$2" extra="${3:-}"
  cat > "/etc/nginx/sites-available/${domain}.conf" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${domain};
    location / {
        proxy_pass http://127.0.0.1:${port};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        ${extra}
    }
}
NGINX
  ln -sf "/etc/nginx/sites-available/${domain}.conf" "/etc/nginx/sites-enabled/${domain}.conf"
}

if [[ $PRODUCTION -eq 1 || -n "$CONSOLE_DOMAIN" ]]; then
  log "Configuring nginx"
  [[ $PRODUCTION -eq 1 ]] && write_vhost "$DOMAIN" 8088
  # Console needs SSE streaming for live deploy logs — disable proxy buffering.
  [[ -n "$CONSOLE_DOMAIN" ]] && write_vhost "$CONSOLE_DOMAIN" 8099 "proxy_buffering off;"
  nginx -t && systemctl reload nginx

  # TLS via certbot (best-effort — DNS must already point at this host).
  log "Requesting Let's Encrypt certificates"
  apt-get install -y -qq certbot python3-certbot-nginx
  CERT_MAIL="${CERTBOT_EMAIL:-${ADMIN_EMAIL:-admin@${DOMAIN:-$CONSOLE_DOMAIN}}}"
  CERT_DOMS=()
  [[ $PRODUCTION -eq 1 ]] && CERT_DOMS+=(-d "$DOMAIN")
  [[ -n "$CONSOLE_DOMAIN" ]] && CERT_DOMS+=(-d "$CONSOLE_DOMAIN")
  if ! certbot --nginx --non-interactive --agree-tos -m "$CERT_MAIL" --redirect "${CERT_DOMS[@]}"; then
    warn "certbot failed (DNS not pointing here yet?). Panel is on HTTP; re-run: certbot --nginx ${CERT_DOMS[*]}"
  fi
fi

# ── Start services ────────────────────────────────────────────────────────
if [[ $START -eq 1 ]]; then
  log "Starting services"
  systemctl restart tetra-host
  [[ $WITH_CONSOLE -eq 1 ]] && systemctl restart tetra-console || true
  sleep 2
  systemctl --no-pager --lines=0 status tetra-host || true
fi

# ── Summary ───────────────────────────────────────────────────────────────
printf '\n\033[1;32mTetra Host installed.\033[0m\n'
if [[ $PRODUCTION -eq 1 ]]; then
  echo "  Panel:   https://${DOMAIN}"
else
  echo "  Panel:   http://127.0.0.1:8088  (no --domain given; add nginx+TLS later to expose it)"
fi
[[ -n "$CONSOLE_DOMAIN" ]] && echo "  Console: https://${CONSOLE_DOMAIN}"
if [[ -n "$ADMIN_EMAIL" ]]; then
  echo "  Admin:   ${ADMIN_EMAIL}"
  [[ "${GENERATED_PW:-0}" -eq 1 ]] && echo "  Password: ${ADMIN_PASSWORD}   <-- generated; save it now"
fi
cat <<'EOF'

Next steps:
  - Edit /opt/tetra-host/.env to wire providers (COOLIFY_*, CLOUDFLARE_API_TOKEN, MAILCOW_*),
    then: systemctl restart tetra-host
  - Logs:  journalctl -u tetra-host -f   (and -u tetra-console if installed)
  - Mail:  run scripts/install-mailcow.sh on a DEDICATED host (see mail-server notes).
EOF
