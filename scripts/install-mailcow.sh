#!/usr/bin/env bash
#
# install-mailcow.sh — quick installer for mailcow-dockerized, intended to run
# on a DEDICATED host (a mail server should own ports 25/465/587/143/993/995).
#
# Usage:
#   MAILCOW_HOSTNAME=mail.example.com [MAILCOW_TZ=Europe/Berlin] \
#   [HTTP_PORT=80] [HTTPS_PORT=443] [MAILCOW_DIR=/opt/mailcow-dockerized] \
#   sudo -E bash scripts/install-mailcow.sh
#
# Set HTTP_PORT/HTTPS_PORT to non-standard values to run behind an existing
# reverse proxy (e.g. 8080/9443); leave default 80/443 on a dedicated host.
#
set -euo pipefail

MAILCOW_HOSTNAME="${MAILCOW_HOSTNAME:-}"
MAILCOW_TZ="${MAILCOW_TZ:-Etc/UTC}"
MAILCOW_DIR="${MAILCOW_DIR:-/opt/mailcow-dockerized}"
HTTP_PORT="${HTTP_PORT:-80}"
HTTPS_PORT="${HTTPS_PORT:-443}"
REPO="https://github.com/mailcow/mailcow-dockerized"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ── Preconditions ─────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root (sudo -E)."
[[ -n "$MAILCOW_HOSTNAME" ]] || die "Set MAILCOW_HOSTNAME=mail.your-domain.tld"
[[ "$MAILCOW_HOSTNAME" == *.*.* ]] || warn "MAILCOW_HOSTNAME should be a FQDN like mail.example.com"

command -v docker >/dev/null || die "Docker is not installed."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 plugin is required."

# RAM / disk advisories
mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
[[ "$mem_mb" -ge 5500 ]] || warn "Only ${mem_mb}MB RAM; mailcow recommends >= 6GB."
free_g=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
[[ "${free_g:-0}" -ge 25 ]] || warn "Only ${free_g}GB free on /; mailcow wants >= 20-30GB."

# Mail ports must be free — this is the #1 reason mailcow fails to start on a
# shared box (e.g. an existing Plesk/Postfix mail server already binds them).
busy=""
for p in 25 465 587 143 993 995; do
  if ss -tln 2>/dev/null | grep -qE "[:.]${p}[[:space:]]"; then busy+=" $p"; fi
done
[[ -z "$busy" ]] || die "Mail ports already in use:${busy}. Another mail server (Plesk/Postfix?) owns them. Use a DEDICATED host for mailcow."

# Chosen web ports must be free
for p in "$HTTP_PORT" "$HTTPS_PORT"; do
  ! ss -tln 2>/dev/null | grep -qE "[:.]${p}[[:space:]]" || die "Web port $p is already in use; pick a free HTTP_PORT/HTTPS_PORT."
done

# Outbound 25 (sending) — frequently blocked by providers (Hetzner/OVH/etc.)
if timeout 6 bash -c "cat < /dev/null > /dev/tcp/gmail-smtp-in.l.google.com/25" 2>/dev/null; then
  log "Outbound port 25 is open."
else
  warn "Outbound port 25 looks BLOCKED — ask your provider to unblock it or mail won't send."
fi

# ── Install ───────────────────────────────────────────────────────────────
umask 0022
if [[ -d "$MAILCOW_DIR/.git" ]]; then
  log "Updating existing mailcow at $MAILCOW_DIR"
  git -C "$MAILCOW_DIR" pull --ff-only
else
  log "Cloning mailcow-dockerized to $MAILCOW_DIR"
  git clone "$REPO" "$MAILCOW_DIR"
fi
cd "$MAILCOW_DIR"

if [[ ! -f mailcow.conf ]]; then
  log "Generating mailcow.conf (hostname=$MAILCOW_HOSTNAME tz=$MAILCOW_TZ)"
  MAILCOW_HOSTNAME="$MAILCOW_HOSTNAME" MAILCOW_TZ="$MAILCOW_TZ" ./generate_config.sh
else
  warn "mailcow.conf already exists; leaving it untouched."
fi

# Apply custom web ports for reverse-proxy coexistence
if [[ "$HTTP_PORT" != "80" || "$HTTPS_PORT" != "443" ]]; then
  log "Setting HTTP_PORT=$HTTP_PORT / HTTPS_PORT=$HTTPS_PORT in mailcow.conf"
  sed -i -E "s/^HTTP_PORT=.*/HTTP_PORT=${HTTP_PORT}/; s/^HTTPS_PORT=.*/HTTPS_PORT=${HTTPS_PORT}/" mailcow.conf
fi

log "Pulling images (this takes a while)…"
docker compose pull
log "Starting mailcow…"
docker compose up -d

cat <<EOF

\033[1;32mmailcow is starting.\033[0m  UI: https://${MAILCOW_HOSTNAME}  (default admin: admin / moohoo — change it!)

Next steps:
  1. DNS for ${MAILCOW_HOSTNAME}:  A/AAAA -> this host;  MX of your domain -> ${MAILCOW_HOSTNAME}
  2. Set rDNS/PTR of this host's IP to ${MAILCOW_HOSTNAME} (at your provider).
  3. Add SPF / DKIM (from the mailcow UI) / DMARC records.
  4. For Tetra Host: create an API key in mailcow UI (Configuration > Access > API),
     then set MAILCOW_URL=https://${MAILCOW_HOSTNAME} and MAILCOW_API_KEY=... in the panel .env.
EOF
