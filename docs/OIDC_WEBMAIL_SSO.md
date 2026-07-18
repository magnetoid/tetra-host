# Passwordless webmail (OIDC SSO)

Tetra acts as an **OIDC Identity Provider** so a tenant already authenticated in
Tetra can open their mailbox in SOGo webmail **without entering a password**.
Mailcow is the OIDC client; when it recognises the Tetra-issued identity it
proxy-auths the browser straight into SOGo (Mailcow's "Proxy Auth").

This is the only way to get true passwordless webmail — Mailcow has **no**
single-use login-link API (mailcow issue #6067). See
`docs/providers/combined-api-reference.md` → *Mailcow OIDC*.

## How the flow works

```
Console "Open webmail" (mailbox X)
      │  GET {PANEL}/oidc/launch?mailbox=X   (Tetra session; verifies ownership)
      ▼
Mailcow OIDC login  ──▶  {PANEL}/oidc/authorize  (Tetra mints a single-use code for X)
      │                        │  302 code → Mailcow redirect_uri
      ▼                        ▼
Mailcow /token ─▶ {PANEL}/oidc/token   (client-secret auth → signed RS256 id_token, email=X)
Mailcow /userinfo ─▶ {PANEL}/oidc/userinfo
      │
      ▼
SOGo opens, logged in as X — no password.
```

**Security invariants** (all covered by `tests/test_oidc.py`):
- The mailbox is asserted **only** after Tetra verifies the session owns it
  (`TenantResource`, fail-closed) — at *both* launch and authorize.
- `redirect_uri` is an **exact-match** allowlist (no open redirect).
- The client authenticates with its secret (constant-time compare).
- Authorization codes are **single-use** and short-lived (5 min); id_tokens are
  RS256-signed and verifiable against `/oidc/jwks`.

> **Origin note.** The flow runs on the **panel** origin (its session + issuer),
> because Mailcow redirects the browser to `{PANEL}/oidc/authorize`. The console's
> "Open webmail" button therefore opens the panel origin; if the operator has no
> live panel session, they log in once. (A follow-up can proxy the OIDC endpoints
> through the console origin for a single-origin experience.)

## 1. Generate a signing key

```bash
scripts/gen-oidc-key.sh          # prints OIDC_PRIVATE_KEY_PEM + the rest of the block
```

## 2. Configure Tetra (panel `.env` / systemd EnvironmentFile)

```dotenv
OIDC_ISSUER=https://panel.cloud-industry.com
OIDC_PRIVATE_KEY_PEM="-----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----\n"
OIDC_CLIENT_ID=mailcow
OIDC_CLIENT_SECRET=<long random secret>
OIDC_REDIRECT_URIS_RAW=https://<mailcow-host>/oidc/callback
OIDC_WEBMAIL_URL=https://<mailcow-host>/
```

Restart the panel. Verify it's live:

```bash
curl -s https://panel.cloud-industry.com/.well-known/openid-configuration | jq .issuer
curl -s https://panel.cloud-industry.com/oidc/jwks | jq '.keys[0].kty'   # "RSA"
```

(Both return 404 while OIDC is unconfigured — that's the dormant state.)

## 3. Configure the console (Next.js env)

```dotenv
PANEL_PUBLIC_URL=https://panel.cloud-industry.com
```

Rebuild the console. The mailbox **Manage** panel now shows **Open webmail**.

## 4. Configure Mailcow (as the OIDC client)

In the Mailcow admin UI: **System → Configuration → Access → Identity Provider →
Generic-OIDC**, then set:

| Mailcow field           | Value                                                        |
|-------------------------|-------------------------------------------------------------|
| Authorization Endpoint  | `https://panel.cloud-industry.com/oidc/authorize`           |
| Token Endpoint          | `https://panel.cloud-industry.com/oidc/token`               |
| User Info Endpoint      | `https://panel.cloud-industry.com/oidc/userinfo`            |
| Client ID               | `mailcow` (must equal `OIDC_CLIENT_ID`)                     |
| Client Secret           | the `OIDC_CLIENT_SECRET` value                              |
| Redirect URL            | Mailcow's own callback — copy it into `OIDC_REDIRECT_URIS_RAW` |
| Client Scopes           | `openid profile email mailcow_template`                     |
| Attribute Mapping       | map `mailcow_template` → your template (e.g. `Default`)     |

Mailcow matches the mailbox by the **`email`** claim, which Tetra sets to the
selected mailbox address. Confirm Mailcow's exact **Redirect URL** in that form
and make sure it appears verbatim in `OIDC_REDIRECT_URIS_RAW` (exact match).

## 5. Test

From the console → **Mail** → a mailbox → **Manage** → **Open webmail**. A new tab
should land in SOGo already signed in. If it bounces to the Mailcow login page,
re-check the Redirect URL match and that `email` is the identifying claim.
