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

## Database migrations (Alembic)

Schema changes are versioned with Alembic (`alembic.ini` + `alembic/`). The
adoption model is deliberate, because the platform has a live database:

- **Fresh / test / dev databases** are materialised by `Base.metadata.create_all`
  on first boot (the fast path) and then **stamped at the current script head** —
  no migration DDL is replayed. See `app.db.session._stamp_alembic_head_if_absent`.
- **Existing databases** (including production) that predate Alembic are stamped
  at head automatically on their next boot — a one-time, no-op reconciliation.
- **Every future schema change** gets its own revision layered on the baseline
  and is applied with `alembic upgrade head` at deploy time. This replaces the
  hand-rolled `_upgrade_existing_schema` ALTER hacks — do not add new columns
  there; write a migration instead.

Day-to-day:

```bash
# Author a migration after changing a model in app/models/
.venv/bin/alembic revision --autogenerate -m "add widget table"
# review the generated file in alembic/versions/, then:
.venv/bin/alembic upgrade head          # apply
.venv/bin/alembic current               # show the applied revision
.venv/bin/alembic downgrade -1          # roll back one (if downgrade() is written)
```

The database URL comes from the app `Settings` (same `DATABASE_URL` as the
running app) — `env.py` reads it, so no URL is hard-coded in `alembic.ini`.

**Deploy order matters:** always run `alembic upgrade head` *before* restarting
the service so the schema is at head when the app boots. `scripts/install.sh`
does this automatically; for a manual `git pull` deploy, run it yourself:

```bash
cd /opt/tetra-host && set -a && source ./.env && set +a
sudo -u tetra .venv/bin/alembic upgrade head
systemctl restart tetra-host
```

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
