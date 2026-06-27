# Tetra Host

Cloud Industry branded multi-tenant hosting panel.

## Stack

- Python FastAPI
- Jinja2 + HTMX
- Tailwind/shadcn-style UI
- SQLite initially
- SQLAlchemy tenant/user/project persistence
- Signed cookie auth
- Coolify API for sites/apps
- Mailcow API for mail
- Cloudflare API for DNS
- Optional Go helper for provider actions

## Native install

```bash
git clone https://github.com/magnetoid/tetra-host.git
cd tetra-host
sudo bash scripts/install.sh
```

Service runs on `127.0.0.1:8088`. Put nginx/Plesk proxy in front.

## Roadmap

1. Skeleton UI and native install
2. Coolify API integration
3. Tenant/customer model + auth ✅
4. Mailcow integration ✅
5. Cloudflare DNS integration ✅
6. Coolify actions + admin controls
7. Audit log + billing/support layers
