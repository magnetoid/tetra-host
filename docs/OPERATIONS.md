# Operations

## Health endpoints

- `/health` confirms the app booted and the plugin registry loaded.
- `/ready` exposes whether provider credentials are configured.

## Provider checks

- Coolify: verify `COOLIFY_URL` and `COOLIFY_TOKEN`, then confirm the `/projects` page lists applications and deployments.
- Mailcow: verify `MAILCOW_URL` and `MAILCOW_API_KEY`, then confirm the `/mail` page lists domains and mailboxes.
- Cloudflare: verify `CLOUDFLARE_API_TOKEN`, then confirm the `/dns` page lists zones and records.

## Admin access

- Bootstrap admin credentials come from `ADMIN_BOOTSTRAP_*` during initial creation.
- To create the first admin or recover an environment, run `scripts/bootstrap-admin.sh`.
- Rotate passwords by updating the local admin record through the application code path before production handoff.

## Runtime hardening

- Keep the app behind `nginx` or another TLS-terminating proxy.
- Use a non-default `APP_SECRET`.
- Enable secure cookies and HTTPS redirect in production.
- Keep provider action toggles disabled until credentials and permissions are verified.

## Production environment contract

- Set `APP_ENV=production`.
- Set `BASE_URL` to the public HTTPS origin, for example `https://panel.cloud-industry.com`.
- Ensure the `BASE_URL` hostname is included in `ALLOWED_HOSTS_RAW`.
- Set `SESSION_HTTPS_ONLY=true` in production.
- Set `FORCE_HTTPS_REDIRECT=true` when the app is served behind the TLS-terminating proxy.
- `scripts/check-production.sh` enforces these settings before `systemd` starts the app.
