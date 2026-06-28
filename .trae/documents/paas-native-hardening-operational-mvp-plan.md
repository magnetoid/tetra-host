# Tetra Host Native Hardening And Operational MVP Plan

## Summary

Upgrade the current single-process FastAPI + Jinja/HTMX panel into a production-ready native-hosted PaaS admin console. The release will keep the existing `systemd` + `nginx` deployment model, replace the placeholder login with real admin authentication, convert the placeholder provider modules into an operational MVP for Coolify/Mailcow/Cloudflare, improve performance and observability, and add deployment safeguards suitable for a first real production rollout.

This plan is based on direct repo inspection of:

- `app/main.py`
- `app/config.py`
- `app/modules/*`
- `app/services/coolify.py`
- `app/services/mailcow.py`
- `app/services/cloudflare.py`
- `app/templates/*`
- `scripts/install.sh`
- `systemd/tetra-host.service`
- `nginx/tetra-host.conf`
- `tests/test_app.py`
- `tests/test_phase2.py`

This plan is also informed by current external guidance:

- FastAPI middleware guidance for `HTTPSRedirectMiddleware`, `TrustedHostMiddleware`, and `GZipMiddleware`: <https://fastapi.tiangolo.com/advanced/middleware/>
- htmx security and progressive enhancement guidance: <https://htmx.org/docs/#security>
- Coolify API authorization, scoping, and permission model: <https://coolify.io/docs/api-reference/authorization>
- Cloudflare API rate-limit behavior and response headers: <https://developers.cloudflare.com/fundamentals/api/reference/limits/>

## Current State Analysis

### Application shape

- The application is a single FastAPI service rooted in `app/main.py`.
- UI is server-rendered with Jinja templates in `app/templates` and htmx loaded from `app/static/js/htmx.min.js`.
- Modules are plugin-based via `app/plugins.py` and `app/modules/__init__.py`.
- The current provider modules are uneven:
  - `app/modules/sites/routes.py` is the only module calling a real provider client (`app/services/coolify.py`).
  - `app/modules/mail/routes.py`, `app/modules/dns/routes.py`, and `app/modules/admin/routes.py` are placeholder pages with static/empty data.
  - `app/modules/dashboard/routes.py` shows static counters and roadmap text.

### Security gaps

- `app/modules/auth/routes.py` accepts any non-empty email/password and redirects to `/dashboard`.
- There is no session middleware, no password hashing flow in use, no protected-route dependency, no logout flow, and no CSRF protection.
- `app/config.py` defaults `app_secret` to `"change-me"`.
- `app/main.py` does not add trusted host, HTTPS redirect, compression, or security-header middleware.
- `nginx/tetra-host.conf` forwards traffic but does not show hardening headers or request limits.
- Provider clients currently have no structured error handling, retry strategy, or least-privilege documentation in-app.

### Functional gaps

- `app/services/mailcow.py` and `app/services/cloudflare.py` only define minimal dataclasses and no operational methods.
- `app/templates/sites/index.html` is visually polished but its action areas are mostly placeholders.
- `app/templates/dashboard/index.html` promises capabilities that the code does not yet deliver.
- Admin/customer functionality is a single static row in `app/modules/admin/routes.py`.

### Performance and resilience gaps

- `app/services/coolify.py` creates a new `httpx.AsyncClient` per request instead of reusing a configured client.
- There is no caching, no rate limiting, no provider backoff, no server-side fragment optimization, and no background refresh strategy.
- No structured logging or request correlation exists in the app.
- `/health` is a very light app-health endpoint and does not reflect provider readiness.

### Testing and delivery gaps

- Test coverage is limited to health, landing page rendering, some static-copy assertions, and Coolify normalization in `tests/test_app.py` and `tests/test_phase2.py`.
- There is no test coverage for auth, sessions, provider failures, route protection, or deployment-sensitive configuration.
- Deployment is manual via `scripts/install.sh`, which performs `rsync -a --delete ./ "$APP_DIR/"` and restarts the service directly.
- The production footprint is host-local `uvicorn` under `systemd/tetra-host.service` behind `nginx/tetra-host.conf`.

## Assumptions And Decisions

### Locked decisions from user input

- Deployment target remains the current native host model (`systemd` + `nginx`) for this release.
- Authentication target is real admin authentication, not full tenant/customer self-service.
- PostgreSQL and Redis are allowed if they materially improve production readiness.
- Provider functionality target is an operational MVP, not a read-only shell and not full destructive provider management everywhere.

### Delivery decisions

- Treat this release as an admin-grade production baseline, not as a fully complete commercial multi-tenant PaaS.
- Keep the plugin architecture and server-rendered HTMX/Jinja approach.
- Use PostgreSQL as the intended production database target while preserving a local-development fallback where helpful.
- Use Redis for rate limiting and short-lived fragment/data caching if the implementation remains small and directly useful.
- Prefer read/list/sync/status workflows plus a narrow, safe set of high-value actions rather than broad write access across all providers.
- Keep deployment native, but make the deployment path safer, repeatable, and rollback-aware.

### Safe operational scope for provider actions

- Coolify: list applications/projects, status, normalized metadata, selected deployment actions such as sync/refresh and deploy trigger if credentials permit.
- Mailcow: list domains, mailboxes, aliases, quotas, and domain health hints; add only the smallest set of write actions if the API surface is clean and testable.
- Cloudflare: list zones and records, expose DNS health signals, and allow tightly scoped record management only after validation and idempotency checks are in place.
- Admin: manage local admin users and platform settings for this release; defer true tenant isolation and billing.

## Proposed Changes

### 1. Stabilize core app construction and configuration

**Files to update**

- `app/main.py`
- `app/config.py`
- `app/templating.py`
- `pyproject.toml`
- `.env.example`

**What**

- Convert the app bootstrap into a production-aware application factory pattern while preserving the current entrypoint.
- Expand settings to include:
  - allowed hosts
  - secure-cookie flags
  - session lifetime
  - CSRF secret / derived signing setup
  - provider timeouts
  - Redis URL
  - PostgreSQL production URL expectations
  - feature toggles for provider actions
- Add middleware for:
  - trusted hosts
  - HTTPS redirect where appropriate for production
  - GZip compression
  - request timing / request ID propagation
  - security headers through custom middleware

**Why**

- The current bootstrap is too thin for a public-facing admin panel and does not enforce production invariants.

**How**

- Preserve `app.main:app` as the runtime object but build it through a factory helper.
- Extend `Settings` in `app/config.py` with typed production fields and validation.
- Use environment-driven behavior so local development remains easy.
- Document the new env contract in `.env.example`.

### 2. Implement real admin authentication and route protection

**Files to update**

- `app/modules/auth/routes.py`
- `app/modules/dashboard/routes.py`
- `app/modules/sites/routes.py`
- `app/modules/mail/routes.py`
- `app/modules/dns/routes.py`
- `app/modules/admin/routes.py`
- `app/templates/auth/login.html`
- `app/templates/base.html`
- `tests/test_app.py`
- `tests/test_phase2.py`

**Files to add**

- `app/modules/auth/schemas.py`
- `app/modules/auth/service.py`
- `app/routes/__init__.py` or another shared dependency location under `app/routes/`
- `app/templates/auth/partials/` fragments if htmx form handling is used

**What**

- Replace the placeholder login with real admin auth using secure password verification, signed server-side session cookies, logout support, and route guards.
- Ensure all panel routes (`/dashboard`, `/sites`, `/mail`, `/dns`, `/admin`) require auth.
- Improve login UX with validation states, error messaging, loading indicators, and accessibility-safe form feedback.

**Why**

- The current app is functionally unsecured.

**How**

- Use existing dependency availability (`passlib[bcrypt]`, `itsdangerous`) for password hashing and signed-session handling, or add a focused session helper if needed.
- Centralize `require_admin_user` / `get_current_admin` dependencies in a shared location rather than duplicating checks in modules.
- Support redirect-back after login and explicit logout.
- Add CSRF protection appropriate for server-rendered forms and htmx posts.

### 3. Add minimal persistent domain models for admin auth and local platform data

**Files to update**

- `pyproject.toml`
- `README.md`

**Files to add**

- `app/models/` for SQLAlchemy models
- `app/db/` for engine, session, and migration helpers
- `alembic.ini` and `alembic/` migration files if not already present
- `tests/` coverage for data-layer behavior

**What**

- Introduce a minimal local persistence layer for:
  - admin users
  - optional audit events
  - cached sync metadata / last-seen provider state pointers
- Make PostgreSQL the intended production path and keep SQLite acceptable for local bootstrapping if that reduces friction.

**Why**

- Real auth and auditability need persistence; SQLite is a weak long-term production target for this control panel.

**How**

- Use SQLAlchemy 2.x in a small, explicit data model.
- Create an initial admin-user migration and seeding/bootstrap path.
- Keep schema scope narrow: only what is needed for real auth, audit logs, and provider sync metadata in this release.

### 4. Refactor provider clients into production-safe service adapters

**Files to update**

- `app/services/coolify.py`
- `app/services/mailcow.py`
- `app/services/cloudflare.py`
- `app/modules/sites/routes.py`
- `app/modules/mail/routes.py`
- `app/modules/dns/routes.py`
- `tests/test_phase2.py`

**Files to add**

- `app/services/http.py` or similar shared HTTP client helper under `app/services/`
- `app/modules/sites/service.py`
- `app/modules/mail/service.py`
- `app/modules/dns/service.py`
- `app/modules/*/schemas.py` where request/response models materially improve validation

**What**

- Create reusable provider adapters with:
  - shared async client lifecycle
  - typed normalization
  - timeout and retry policy
  - clear exception mapping
  - rate-limit aware backoff
  - redacted logging
- Expand functionality:
  - Coolify: projects/apps/status/environment/domain metadata
  - Mailcow: domains/mailboxes/aliases/quota and admin-safe summaries
  - Cloudflare: zones/records plus DNS health hints and pagination support

**Why**

- Current integrations are too thin for an operational panel and will fail noisily in production.

**How**

- Add a shared HTTP utility to reduce repeated `httpx.AsyncClient` construction.
- Handle provider auth and permission failures explicitly.
- Respect external platform guidance:
  - Coolify token scoping and permission shape
  - Cloudflare pagination and `429`/`Retry-After` handling
- Keep action endpoints narrow, auditable, and validated.

### 5. Turn dashboard and provider pages into an operational MVP

**Files to update**

- `app/modules/dashboard/routes.py`
- `app/modules/sites/routes.py`
- `app/modules/mail/routes.py`
- `app/modules/dns/routes.py`
- `app/modules/admin/routes.py`
- `app/templates/dashboard/index.html`
- `app/templates/sites/index.html`
- `app/templates/mail/index.html`
- `app/templates/dns/index.html`
- `app/templates/admin/index.html`
- `app/templates/base.html`

**Files to add**

- `app/templates/dashboard/partials/`
- `app/templates/sites/partials/`
- `app/templates/mail/partials/`
- `app/templates/dns/partials/`
- `app/templates/admin/partials/`

**What**

- Replace static counts and placeholder rows with live, resilient provider-backed summaries.
- Introduce operational UI patterns:
  - sync status cards
  - empty states with next-step guidance
  - degraded-state messaging when provider credentials are missing
  - server-rendered filters/search where useful
  - htmx partial refresh for tables/cards
  - action confirmation flows for any provider write operation

**Why**

- The current UI looks polished but does not yet act like a production admin console.

**How**

- Keep semantic HTML and progressive enhancement first.
- Use htmx for partial reloads only where it improves responsiveness and reduces full-page refreshes.
- Add accessible loading indicators, focus retention, and clear inline errors.
- Align UX copy with actual implemented behavior so the dashboard stops overpromising unfinished functionality.

### 6. Add caching, rate limiting, and observability

**Files to update**

- `app/main.py`
- `app/config.py`
- `app/modules/dashboard/routes.py`
- `app/modules/sites/routes.py`
- `app/modules/mail/routes.py`
- `app/modules/dns/routes.py`
- `systemd/tetra-host.service`
- `nginx/tetra-host.conf`

**Files to add**

- `app/observability.py` or equivalent under `app/`
- `app/cache.py` and/or `app/rate_limit.py`
- Tests that cover failure modes and throttling behavior

**What**

- Add:
  - structured application logging
  - request IDs / correlation IDs
  - improved `/health` and possibly `/ready` semantics
  - Redis-backed or lightweight in-process caching where appropriate
  - login rate limiting
  - provider sync throttling
  - static and fragment cache headers where safe

**Why**

- Operational resilience and abuse resistance are currently missing.

**How**

- Keep caching targeted:
  - dashboard summaries
  - provider list fragments
  - static provider metadata
- Do not cache user-specific HTML without safe keys.
- Add explicit no-store behavior for auth pages and sensitive panels.
- Use rate limits at both app and proxy layers when feasible.

### 7. Harden native deployment and production configuration

**Files to update**

- `scripts/install.sh`
- `systemd/tetra-host.service`
- `nginx/tetra-host.conf`
- `README.md`
- `.env.example`

**Files to add**

- `scripts/check-production.sh`
- `scripts/bootstrap-admin.sh`
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS.md`

**What**

- Replace the risky deployment story with a safer native release path.
- Improve the service and proxy configuration with:
  - environment validation before restart
  - safer ownership/permissions
  - clearer restart policy
  - forwarded-header correctness
  - security headers
  - optional proxy-side request limiting
  - explicit health-check verification

**Why**

- Current deployment is manual and destructive, with limited safety rails.

**How**

- Keep `install.sh`, but make it idempotent, explicit, and less dangerous.
- Split initial bootstrap tasks from upgrade/redeploy tasks.
- Add preflight checks for Python env, required env vars, database availability, Redis availability, and writable directories.
- Document the exact production rollout and rollback procedure.

### 8. Expand automated verification to match production risk

**Files to update**

- `tests/test_app.py`
- `tests/test_phase2.py`
- `pytest.ini`
- `pyproject.toml`

**Files to add**

- `tests/test_auth.py`
- `tests/test_dashboard.py`
- `tests/test_sites.py`
- `tests/test_mail.py`
- `tests/test_dns.py`
- `tests/test_admin.py`
- `tests/conftest.py`

**What**

- Add focused tests for:
  - auth success/failure/logout
  - protected route redirects
  - CSRF/session expectations
  - provider success/degraded/failure states
  - dashboard summaries
  - rate-limit behavior where practical
  - install/config preflight helpers

**Why**

- The current test suite is not sufficient for a production hardening release touching auth, provider services, and deployment behavior.

**How**

- Use mocking around provider HTTP calls.
- Keep tests high-value and behavior-driven, not snapshot-heavy.
- Add a lint and diagnostics pass as part of implementation verification.

## Execution Sequence

1. Build the app factory, settings expansion, and shared middleware.
2. Introduce the persistence layer and admin-user model/migration/bootstrap path.
3. Implement real admin auth and protect all panel routes.
4. Refactor provider clients and route-layer service boundaries.
5. Replace placeholder dashboard/mail/dns/admin data with real provider-backed summaries.
6. Add htmx partials, UX polish, loading/error/empty states, and accessibility refinements.
7. Add caching, rate limiting, logging, and health/readiness improvements.
8. Harden install, `systemd`, and `nginx` deployment assets plus production docs.
9. Expand tests and run the full verification matrix before any deployment.
10. Deploy to the current native target host and run post-deploy smoke checks.

## Verification Steps

### Local verification

- Run Ruff on the changed Python files.
- Run the full pytest suite.
- Verify no diagnostics remain in recently edited files.
- Manually test:
  - login failure and success
  - logout
  - protected-route redirect behavior
  - dashboard rendering with missing provider credentials
  - dashboard rendering with mocked/real provider responses
  - sites/mail/dns/admin views in healthy and degraded states

### Integration verification

- Validate provider adapters against current API expectations using non-destructive read endpoints first.
- Confirm Coolify token scope is sufficient but not over-privileged.
- Confirm Cloudflare behavior under paginated responses and simulated `429` responses.
- Confirm Mailcow connectivity over HTTPS and with SSL verification enabled.

### Deployment verification

- Run deployment preflight checks on the target host.
- Verify database migration / bootstrap completion.
- Verify service startup under `systemd`.
- Verify `nginx` proxy correctness and security headers.
- Verify `/health` and any readiness endpoint through the reverse proxy.
- Perform post-deploy smoke tests for login, dashboard, sites, mail, dns, and admin pages.
- Review application logs for provider exceptions, header misconfiguration, or auth/session errors.

## Risks And Mitigations

- Risk: auth and persistence work expands scope quickly.
  - Mitigation: keep the local data model minimal and admin-only.
- Risk: provider write actions can cause destructive side effects.
  - Mitigation: default to read/list/sync first and add only tightly scoped, validated actions.
- Risk: introducing both PostgreSQL and Redis increases rollout complexity.
  - Mitigation: make each optional behind config checks, but require PostgreSQL for production if feasible.
- Risk: native-host deployment may drift from local development.
  - Mitigation: add explicit preflight scripts, docs, and post-deploy smoke checks.

## Out Of Scope For This Release

- Full tenant/customer self-service onboarding
- Billing and Stripe integration
- Deep RBAC / per-tenant isolation
- Full Docker/Kubernetes/Coolify migration of this control panel itself
- Large-scale background job orchestration beyond what is required for safe sync and rate control
