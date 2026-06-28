# Deployment

## Native host rollout

1. Sync the repository to the target host.
2. Review `.env` and confirm:
   - `APP_SECRET` is rotated
   - `DATABASE_URL` points to the intended runtime database
   - provider credentials are present and least-privileged
   - `SESSION_HTTPS_ONLY=true` behind TLS
3. Run:

```bash
sudo bash scripts/install.sh
```

4. Create or confirm the bootstrap admin:

```bash
sudo ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='replace-me' bash scripts/bootstrap-admin.sh
```

5. Verify:
   - `systemctl status tetra-host --no-pager`
   - `curl http://127.0.0.1:8088/health`
   - reverse-proxy access through `nginx`

## Safer upgrade workflow

1. Pull the new release to the host.
2. Run `scripts/check-production.sh`.
3. Re-run `scripts/install.sh`.
4. Smoke test `/auth/login`, `/dashboard`, `/sites`, `/mail`, `/dns`, and `/admin`.

## Rollback

1. Re-deploy the previous known-good revision.
2. Re-run `scripts/install.sh`.
3. Confirm health and login behavior.
