#!/usr/bin/env bash
# Repoint an nginx vhost from Coolify's Traefik to an engine loopback port (or back).
#
# Imported apps that Coolify served only through its proxy end their cutover with
# "ACTION NEEDED: point nginx for <hosts> at http://127.0.0.1:<port>". The panel cannot
# write /etc/nginx, so an operator runs this as root. It backs the vhost up, swaps the
# upstream, validates with `nginx -t` and reloads; on a failed test it restores the backup.
#
#   scripts/nginx-repoint.sh /etc/nginx/conf.d/morpheus.direct.conf 9200   # → engine
#   scripts/nginx-repoint.sh /etc/nginx/conf.d/morpheus.direct.conf restore # → last backup
set -euo pipefail

conf=${1:?vhost file}
target=${2:?port or "restore"}
[[ -f $conf ]] || { echo "no such file: $conf" >&2; exit 1; }

if [[ $target == restore ]]; then
  backup=$(ls -1t "$conf".bak.tetra-* 2>/dev/null | head -1)
  [[ -n $backup ]] || { echo "no backup for $conf" >&2; exit 1; }
  cp -p "$backup" "$conf"
else
  [[ $target =~ ^[0-9]+$ ]] || { echo "port must be a number" >&2; exit 1; }
  grep -q 'proxy_pass https://127.0.0.1:8445;' "$conf" \
    || { echo "$conf does not proxy to Coolify's Traefik; refusing" >&2; exit 1; }
  backup="$conf.bak.tetra-$(date +%Y%m%d%H%M%S)"
  cp -p "$conf" "$backup"
  sed -E -i \
    -e "s|proxy_pass https://127.0.0.1:8445;|proxy_pass http://127.0.0.1:${target};|" \
    -e '/proxy_ssl_(verify|server_name|name) /d' \
    "$conf"
fi

if nginx -t 2>/dev/null; then
  systemctl reload nginx
  echo "ok: $conf now proxies to: $(grep -o 'proxy_pass [^;]*' "$conf" | grep -v ':8081' | sort -u | tr '\n' ' ')"
else
  [[ $target == restore ]] || cp -p "$backup" "$conf"
  nginx -t || true
  echo "nginx -t failed; $conf left unchanged" >&2
  exit 1
fi
