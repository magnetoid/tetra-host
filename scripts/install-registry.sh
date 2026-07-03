#!/usr/bin/env bash
# Run a local Docker registry for Tetra rollback durability (ADR 0014).
#
# Idempotent: safe to re-run. Binds to 127.0.0.1 only (panel-local; never expose it),
# stores blobs in /var/lib/tetra-registry, and enables manifest/tag deletion so the
# panel's retention window (REGISTRY_KEEP_IMAGES) can drop old tags.
#
# After install, set in the panel .env:   REGISTRY_URL=127.0.0.1:5000
#
# Retention untags in the registry; blob space is reclaimed by an OFFLINE garbage
# collect. Never GC the live container (an in-flight push can corrupt the store) —
# stop, GC in a transient container, start:
#   docker stop tetra-registry \
#     && docker run --rm -v /var/lib/tetra-registry:/var/lib/registry registry:3 \
#          garbage-collect --delete-untagged /etc/distribution/config.yml \
#     && docker start tetra-registry
# (A push landing in the brief stop window is already handled: the panel's push is
# best-effort and falls back to the local-only image.) Example cron, Sundays 04:17:
#   17 4 * * 0  docker stop tetra-registry && docker run --rm -v /var/lib/tetra-registry:/var/lib/registry registry:3 garbage-collect --delete-untagged /etc/distribution/config.yml; docker start tetra-registry
set -euo pipefail

PORT="${REGISTRY_PORT:-5000}"
DATA_DIR="${REGISTRY_DATA_DIR:-/var/lib/tetra-registry}"
NAME=tetra-registry

if docker inspect "$NAME" >/dev/null 2>&1; then
  # An existing container without delete enabled would make retention silently no-op.
  if ! docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NAME" \
      | grep -qx 'REGISTRY_STORAGE_DELETE_ENABLED=true'; then
    echo "✗ $NAME exists but manifest deletion is DISABLED — retention would silently no-op." >&2
    echo "  Recreate it: docker rm -f $NAME && $0" >&2
    exit 1
  fi
  echo "✓ $NAME already exists — ensuring it is running"
  docker start "$NAME" >/dev/null
else
  mkdir -p "$DATA_DIR"
  docker run -d \
    --name "$NAME" \
    --restart unless-stopped \
    -p "127.0.0.1:${PORT}:5000" \
    -v "$DATA_DIR:/var/lib/registry" \
    -e REGISTRY_STORAGE_DELETE_ENABLED=true \
    registry:3 >/dev/null
  echo "✓ started $NAME on 127.0.0.1:${PORT} (data: $DATA_DIR)"
fi

curl -fsS "http://127.0.0.1:${PORT}/v2/" >/dev/null && echo "✓ registry API answering on /v2/"
echo "→ set REGISTRY_URL=127.0.0.1:${PORT} in the panel .env and restart tetra-host"
