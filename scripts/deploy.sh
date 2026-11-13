#!/usr/bin/env bash
#
# deploy.sh — roll a Tetra Host server forward to the latest code, safely and in order.
#
#   sudo scripts/deploy.sh                    # backend + console from origin/main
#   sudo scripts/deploy.sh --ref my-branch    # deploy another branch
#   sudo scripts/deploy.sh --backend-only     # skip the console build
#   sudo scripts/deploy.sh --console-only     # rebuild the console only
#   sudo scripts/deploy.sh --rollback-console # switch the console back to its previous build
#
# Backend: back up the database → pull → install deps → migrate → preflight → restart →
# wait for /ready. Nothing is restarted if an earlier step fails.
#
# Console: built into the idle one of two slots (apps/web/.next-a, .next-b) while the
# current build keeps serving; the service is switched to the new slot only after the
# build succeeds, and switched back if the new build doesn't answer. The active slot is
# recorded in data/console.env (TETRA_NEXT_DIST_DIR), read by tetra-console.service.
#
# Env overrides: APP_DIR (/opt/tetra-host), USER_NAME (tetrahost), NODE_DIR (directory
# with node + pnpm; default $APP_DIR/.node/bin when present), KEEP_BACKUPS (10).
#
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/tetra-host}"
USER_NAME="${USER_NAME:-tetrahost}"
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"
REF="main"
DO_BACKEND=1
DO_CONSOLE=1
ROLLBACK_CONSOLE=0

WEB_DIR="$APP_DIR/apps/web"
CONSOLE_ENV="$APP_DIR/data/console.env"
BACKUP_DIR="$APP_DIR/data/backups"

STEP="starting"
log()  { STEP="$*"; printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }
trap 'printf "\033[1;31m[error]\033[0m deploy stopped during: %s\n" "$STEP" >&2' ERR

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)              REF="${2:?--ref needs a branch}"; shift 2 ;;
    --backend-only)     DO_CONSOLE=0; shift ;;
    --console-only)     DO_BACKEND=0; shift ;;
    --rollback-console) ROLLBACK_CONSOLE=1; DO_BACKEND=0; DO_CONSOLE=0; shift ;;
    -h|--help)          usage ;;
    *) die "Unknown option: $1 (try --help)" ;;
  esac
done

[[ $EUID -eq 0 ]] || die "Run as root (sudo scripts/deploy.sh)."
[[ -d "$APP_DIR/.git" ]] || die "$APP_DIR is not a git checkout."

# One deploy at a time.
exec 9>/run/tetra-deploy.lock
flock -n 9 || die "Another deploy is running."

as_app() { sudo -u "$USER_NAME" -H env PATH="$PATH" "$@"; }
in_app() { as_app bash -c "cd '$APP_DIR' && set -a && . ./.env && set +a && $*"; }

# Wait until a URL answers with HTTP 200 (extra curl args after the URL).
wait_for_200() {
  local url="$1" seconds="$2"; shift 2
  local code=""
  for _ in $(seq "$seconds"); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$@" "$url" || true)"
    [[ "$code" == "200" ]] && return 0
    sleep 1
  done
  warn "$url answered ${code:-nothing} after ${seconds}s"
  return 1
}

# ── Console slots ─────────────────────────────────────────────────────────
console_setting() {
  [[ -f "$CONSOLE_ENV" ]] && sed -n "s/^$1=//p" "$CONSOLE_ENV" || true
}
active_slot()   { local s; s="$(console_setting TETRA_NEXT_DIST_DIR)"; printf '%s' "${s:-.next}"; }
previous_slot() { console_setting TETRA_NEXT_PREVIOUS_DIST_DIR; }

other_slot() { [[ "$1" == ".next-a" ]] && printf '.next-b' || printf '.next-a'; }

switch_console() {
  local slot="$1" previous="$2" tmp
  tmp="$(mktemp "$APP_DIR/data/.console.env.XXXXXX")"
  printf 'TETRA_NEXT_DIST_DIR=%s\nTETRA_NEXT_PREVIOUS_DIST_DIR=%s\n' "$slot" "$previous" > "$tmp"
  chmod 0644 "$tmp"
  mv -f "$tmp" "$CONSOLE_ENV"
  systemctl restart tetra-console
}

console_answers() { wait_for_200 "http://127.0.0.1:8099/auth/login" 30; }

if [[ $DO_CONSOLE -eq 1 || $ROLLBACK_CONSOLE -eq 1 ]]; then
  NODE_DIR="${NODE_DIR:-}"
  [[ -z "$NODE_DIR" && -x "$APP_DIR/.node/bin/node" ]] && NODE_DIR="$APP_DIR/.node/bin"
  [[ -n "$NODE_DIR" ]] && export PATH="$NODE_DIR:$PATH"
  command -v node >/dev/null || die "node not found (set NODE_DIR)."
  node_major="$(node -v | sed -n 's/^v\([0-9]\{1,\}\).*/\1/p')"
  [[ "${node_major:-0}" -ge 22 ]] || die "Node 22+ required for the console, found $(node -v)."
  command -v pnpm >/dev/null || die "pnpm not found next to node (corepack enable)."
fi

if [[ $ROLLBACK_CONSOLE -eq 1 ]]; then
  current="$(active_slot)"
  previous="$(previous_slot)"
  [[ -n "$previous" && -f "$WEB_DIR/$previous/BUILD_ID" ]] \
    || die "No previous console build to go back to."
  log "Switching the console back from $current to $previous"
  switch_console "$previous" "$current"
  console_answers || die "The previous console build does not answer either."
  ok "console serving $previous"
  exit 0
fi

# ── Backend ───────────────────────────────────────────────────────────────
PREV_COMMIT="$(as_app git -C "$APP_DIR" rev-parse --short HEAD)"

if [[ $DO_BACKEND -eq 1 ]]; then
  log "Checking the working tree"
  as_app git -C "$APP_DIR" diff --quiet HEAD -- \
    || die "Tracked files in $APP_DIR have local changes; commit or discard them first."

  log "Backing up the database"
  db_info="$(in_app ".venv/bin/python -c 'from app.config import get_settings; from sqlalchemy.engine import make_url; u = make_url(get_settings().database_url); print(u.get_backend_name(), u.database or \"\")'")"
  db_backend="${db_info%% *}"
  db_path="${db_info#* }"
  if [[ "$db_backend" == "sqlite" ]]; then
    [[ "$db_path" == /* ]] || db_path="$APP_DIR/${db_path#./}"
    as_app mkdir -p "$BACKUP_DIR"
    backup="$BACKUP_DIR/$(basename "$db_path" .db)-$(date +%Y%m%d-%H%M%S)-$PREV_COMMIT.db"
    as_app sqlite3 "$db_path" ".backup '$backup'"
    [[ "$(as_app sqlite3 -readonly "$backup" 'pragma integrity_check;')" == "ok" ]] \
      || die "Backup $backup failed its integrity check."
    ok "backup: $backup"
    # Keep the newest KEEP_BACKUPS automatic backups.
    find "$BACKUP_DIR" -maxdepth 1 -name '*.db' -printf '%T@ %p\n' | sort -rn \
      | tail -n "+$((KEEP_BACKUPS + 1))" | cut -d' ' -f2- | xargs -r rm -f --
  else
    warn "Database is $db_backend; back it up with its own tools (not done here)."
  fi

  log "Pulling origin/$REF"
  as_app git -C "$APP_DIR" fetch -q origin "$REF"
  as_app git -C "$APP_DIR" reset -q --hard "origin/$REF"
  NEW_COMMIT="$(as_app git -C "$APP_DIR" rev-parse --short HEAD)"
  ok "$PREV_COMMIT → $NEW_COMMIT"

  log "Installing Python dependencies"
  as_app "$APP_DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$APP_DIR/requirements.txt"

  log "Running database migrations"
  in_app ".venv/bin/alembic upgrade head"

  log "Checking production configuration"
  as_app env APP_DIR="$APP_DIR" "$APP_DIR/scripts/check-production.sh"

  log "Restarting the backend"
  systemctl restart tetra-host
  if ! wait_for_200 "http://127.0.0.1:8088/ready" 30 -H "X-Forwarded-Proto: https"; then
    journalctl -u tetra-host -n 30 --no-pager >&2 || true
    die "Backend not ready. To go back: git -C $APP_DIR reset --hard $PREV_COMMIT, restore ${backup:-the database backup}, restart tetra-host."
  fi
  ok "backend ready"
fi

# ── Console ───────────────────────────────────────────────────────────────
if [[ $DO_CONSOLE -eq 1 ]]; then
  current="$(active_slot)"
  current_previous="$(previous_slot)"
  next="$(other_slot "$current")"

  log "Installing console dependencies"
  as_app bash -c "cd '$WEB_DIR' && pnpm install --frozen-lockfile --reporter=silent"

  log "Building the console into $next (still serving $current)"
  as_app rm -rf "$WEB_DIR/$next"
  as_app bash -c "cd '$WEB_DIR' && NODE_ENV=production TETRA_NEXT_DIST_DIR='$next' pnpm build" \
    > "$APP_DIR/logs/console-build.log" 2>&1 \
    || { tail -n 30 "$APP_DIR/logs/console-build.log" >&2; die "Console build failed; $current is still serving."; }
  [[ -f "$WEB_DIR/$next/BUILD_ID" ]] || die "Console build left no BUILD_ID; $current is still serving."
  # `next build` may add its build folder's type paths to tsconfig.json; keep the
  # checkout clean so the next deploy's working-tree check passes.
  as_app git -C "$APP_DIR" checkout -q -- apps/web/tsconfig.json

  log "Switching the console to $next"
  switch_console "$next" "$current"
  if ! console_answers; then
    journalctl -u tetra-console -n 20 --no-pager >&2 || true
    warn "New console build does not answer; switching back to $current"
    switch_console "$current" "$current_previous"
    console_answers || warn "$current does not answer either."
    die "Console deploy failed and was rolled back to $current."
  fi
  ok "console serving $next (previous build kept in $current; --rollback-console to go back)"
fi

STEP="done"
ok "deploy finished at $(as_app git -C "$APP_DIR" rev-parse --short HEAD)"
