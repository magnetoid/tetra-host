#!/usr/bin/env bash
# Generate an RSA signing key for the Tetra OIDC Identity Provider (passwordless
# webmail SSO). Prints the PEM as a single-line value ready for OIDC_PRIVATE_KEY_PEM
# in .env / the systemd EnvironmentFile.
#
# Usage:
#   scripts/gen-oidc-key.sh              # print key + guidance
#   scripts/gen-oidc-key.sh --raw        # print only the PEM (multi-line)
set -euo pipefail

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# 2048-bit RSA, PKCS#8 PEM — matches app/services/oidc_keys.py expectations.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$tmp" 2>/dev/null

if [[ "${1:-}" == "--raw" ]]; then
  cat "$tmp"
  exit 0
fi

echo "# Tetra OIDC signing key (RSA-2048). Keep this SECRET."
echo "# Put it in .env as OIDC_PRIVATE_KEY_PEM. For a single-line env value, the"
echo "# app accepts literal \\n — or use an EnvironmentFile that supports multi-line."
echo
echo "OIDC_PRIVATE_KEY_PEM=\"$(awk 'BEGIN{ORS="\\n"} {print}' "$tmp")\""
echo
echo "# Then set the rest of the OIDC block (see .env.example):"
echo "#   OIDC_ISSUER=https://panel.cloud-industry.com"
echo "#   OIDC_CLIENT_ID=mailcow"
echo "#   OIDC_CLIENT_SECRET=<generate a long random secret>"
echo "#   OIDC_REDIRECT_URIS_RAW=https://<mailcow-host>/oidc/callback  (verify exact path in Mailcow UI)"
echo "#   OIDC_WEBMAIL_URL=https://<mailcow-host>/  (where the 'Open webmail' button sends the browser)"
echo "# and configure the matching client inside Mailcow — see docs/OIDC_WEBMAIL_SSO.md."
