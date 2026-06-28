# Tetra Host

Cloud Industry branded multi-tenant hosting panel.

## Stack

- Python FastAPI
- Jinja2 + HTMX
- Tailwind/shadcn-style UI
- Async SQLAlchemy
- Coolify API for sites/apps
- Mailcow API for mail
- Cloudflare API for DNS
- Signed admin sessions and protected routes

## Native install

```bash
git clone https://github.com/magnetoid/tetra-host.git
cd tetra-host
sudo bash scripts/install.sh
sudo ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='***' bash scripts/bootstrap-admin.sh
```

Service runs on `127.0.0.1:8088`. Put nginx/Plesk proxy in front.

## Production notes

- Copy `.env.example` to `.env` and set a real `APP_SECRET`.
- Prefer PostgreSQL in production by setting `DATABASE_URL=postgresql://...`.
- Use `scripts/check-production.sh` before restarting the service.
- Set `SESSION_HTTPS_ONLY=true` and `FORCE_HTTPS_REDIRECT=true` behind TLS.
- Enable `ENABLE_PROVIDER_ACTIONS=true` only after validating provider credentials and permissions.

## Roadmap

1. Hardened native runtime and real admin auth
2. Coolify operational inventory and deploy actions
3. Mailcow domain/mailbox visibility
4. Cloudflare zone and record visibility
5. Audit log + deeper admin controls
6. Tenant/customer model + billing