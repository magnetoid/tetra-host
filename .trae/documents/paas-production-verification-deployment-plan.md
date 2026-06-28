# PaaS Production Verification And Deployment Plan

## Summary

Complete the enhancement request by treating the current repository as an almost-finished production hardening release, then executing a final delivery cycle focused on three outcomes:

- validate that the new FastAPI-based admin control plane is fully functional, secure, performant, and aligned with modern server-rendered PaaS operational patterns;
- close any remaining implementation gaps discovered during verification, especially around production proxy behavior, UX polish, provider degradation states, and deployment safety;
- deploy and verify the release on the native target server behind the real domain `panel.cloud-industry.com`.

This continuation plan is grounded in direct inspection of the current repository state, especially:

- `app/main.py`
- `app/config.py`
- `app/modules/auth/routes.py`
- `app/modules/dashboard/routes.py`
- `app/modules/sites/routes.py`
- `app/modules/mail/routes.py`
- `app/modules/dns/routes.py`
- `app/modules/admin/routes.py`
- `app/services/coolify.py`
- `app/services/mailcow.py`
- `app/services/cloudflare.py`
- `scripts/install.sh`
- `systemd/tetra-host.service`
- `nginx/tetra-host.conf`
- `docs/DEPLOYMENT.md`
- `tests/test_auth.py`
- `tests/test_phase2.py`

It is also informed by current external guidance and current docs:

- FastAPI and Starlette middleware guidance for `TrustedHostMiddleware`, `HTTPSRedirectMiddleware`, `GZipMiddleware`, and secure session cookies: <https://fastapi.tiangolo.com/advanced/middleware/> and <https://github.com/Kludex/starlette/blob/main/docs/middleware.md>
- HTMX security guidance for CSRF, progressive enhancement, and HTML trust boundaries: <https://htmx.org/docs/#csrf-prevention> and <https://four.htmx.org/docs/security/best-practices>
- SQLAlchemy async guidance for engine/session lifecycle and avoiding unsafe async-session patterns: <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- Cloudflare API rate-limit guidance, including `429` handling and `Retry-After`: <https://developers.cloudflare.com/fundamentals/api/reference/limits/>
- Coolify deployment-token and deployment-trigger guidance: <https://next.coolify.io/docs/applications/ci-cd/github/actions>
- NGINX request-limiting guidance for proxied applications: <https://docs.nginx.com/nginx/admin-guide/security-controls/controlling-access-proxied-http/>

## Current State Analysis

### Application state

- The repository is no longer a placeholder prototype. The core hardening phase appears implemented:
  - `app/main.py` now initializes shared app state, middleware, DB setup, request observability, `/health`, and `/ready`.
  - `app/config.py` includes production-aware settings for trusted hosts, secure sessions, login rate limiting, provider caching, and provider credentials.
  - `app/db/` and `app/models/` provide async SQLAlchemy-backed persistence for admin auth and audit groundwork.
  - `app/modules/auth/` now uses DB-backed authentication with password hashing, CSRF validation, logout, and login throttling.
  - provider-backed operational pages exist for sites, mail, DNS, dashboard, and admin.

### UX and operational maturity

- The login experience and panel shell are already substantially improved compared with the original placeholder state.
- The dashboard and operational pages now expose real provider data, but execution should still verify:
  - graceful behavior when providers are unreachable or only partially configured;
  - consistency of empty states, inline error messaging, and refresh behavior;
  - whether any templates still overpromise features or expose incomplete actions.

### Performance and resilience

- The app already uses:
  - a shared `httpx.AsyncClient`;
  - a small TTL cache;
  - an in-memory rate limiter;
  - GZip compression;
  - request IDs and timing headers.
- The remaining performance work should be verification-driven rather than speculative. Any new change must be justified by a confirmed issue found in test or live behavior.

### Security state

- The app already includes the primary controls expected for this release:
  - signed session cookies;
  - CSRF tokens on form posts;
  - trusted-host validation;
  - optional HTTPS redirect;
  - security headers;
  - login rate limiting;
  - password hashing.
- The only explicitly known unresolved security/runtime issue from the previous session is the production host/proxy mismatch that caused `Invalid host header` before the live `.env` was corrected.

### Testing and deployment state

- The test suite now includes auth, admin, app, and phase-2 behavior coverage.
- Deployment assets are present and already hardened:
  - `scripts/check-production.sh`
  - `scripts/bootstrap-admin.sh`
  - `scripts/install.sh`
  - `systemd/tetra-host.service`
  - `nginx/tetra-host.conf`
  - `docs/DEPLOYMENT.md`
  - `docs/OPERATIONS.md`
- The last known execution state from the previous session was:
  - code deployed to the target host;
  - service healthy on loopback;
  - production `.env` corrected for domain and HTTPS behavior;
  - `tetra-host` restarted;
  - final public-domain post-restart verification still pending.

## Assumptions And Decisions

### Locked decisions

- The deployment target remains the existing native host setup with `systemd` and an NGINX/Plesk reverse-proxy layer.
- The public application domain for verification is `panel.cloud-industry.com`.
- The target server remains the existing remote host described in session context; execution will use the already-established server credentials and native deployment path rather than trying to switch deployment targets.
- The release scope is an admin-grade operational PaaS console, not a full customer-facing multi-tenant SaaS.

### Planning decisions

- Do not re-architect the app again. Treat the current codebase as the baseline and make only targeted corrections discovered by verification.
- Prefer official docs and vendor docs over blog guidance when deciding on final fixes.
- Prefer fixes that improve correctness, operator safety, and UX clarity over adding broad new feature surface area late in the rollout.
- Keep deployment native and incremental. Do not introduce containers, Coolify self-hosting of this panel, or a new CI/CD path in this release.
- Any provider write action remains opt-in and tightly scoped behind existing configuration gates.

### Acceptance criteria

- Local verification passes for lint, tests, and diagnostics.
- Authentication works end to end with secure redirects and logout.
- Protected routes correctly redirect unauthenticated users.
- Provider-backed pages render acceptably in both configured and degraded states.
- Reverse-proxy production access works through the real domain without host-header errors.
- Public smoke checks pass for `/health`, `/auth/login`, and authenticated navigation to `/dashboard`, `/sites`, `/mail`, `/dns`, and `/admin`.

## Proposed Changes

### 1. Re-audit the implemented code against current best practices

**Files to inspect and possibly update**

- `app/main.py`
- `app/config.py`
- `app/observability.py`
- `app/routes/__init__.py`
- `app/routes/deps.py`
- `app/modules/auth/routes.py`
- `app/templates/base.html`
- `app/templates/auth/login.html`

**What**

- Compare the implemented middleware, session, CSRF, redirect, and request-context behavior against current FastAPI, Starlette, and HTMX guidance.
- Fix only concrete issues discovered in the audit, with special attention to:
  - host/proxy correctness behind TLS termination;
  - no-store behavior on auth-sensitive responses if missing;
  - trusted-host coverage for the real production domain and loopback;
  - template-level UX inconsistencies for auth and error states.

**Why**

- The major security work is in place, but the one known production issue sits exactly at the boundary between middleware, proxy headers, and real-domain behavior.

**How**

- Read the current implementations first.
- Verify whether additional response headers or auth-page cache controls are needed.
- Keep any fixes narrow and backed by either docs or an observed failure mode.

### 2. Verify provider adapters and degrade-state UX end to end

**Files to inspect and possibly update**

- `app/services/http.py`
- `app/services/coolify.py`
- `app/services/mailcow.py`
- `app/services/cloudflare.py`
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

**What**

- Validate that provider timeouts, error handling, retries, and cached reads behave as intended for:
  - missing credentials;
  - upstream `4xx` auth failures;
  - upstream `429` throttling;
  - network failures and empty responses.
- Improve operator UX where pages currently fail unclearly, truncate too aggressively, or do not guide the admin toward a fix.

**Why**

- The user explicitly asked for deeper research and for visible incomplete functionality to be fixed. The highest-value remaining risk is not a missing module, but unclear degraded-state behavior in the operational pages.

**How**

- Start with the existing tests and route behavior.
- Add or refine targeted tests only where they materially reduce regression risk.
- Use Cloudflare and Coolify guidance to validate retry/backoff expectations and safe action gating.

### 3. Complete the verification matrix before any final server push

**Files to inspect and possibly update**

- `tests/conftest.py`
- `tests/test_app.py`
- `tests/test_auth.py`
- `tests/test_admin.py`
- `tests/test_phase2.py`
- `pyproject.toml`
- `pytest.ini`

**What**

- Run a complete verification cycle covering:
  - lint;
  - automated tests;
  - diagnostics on edited files;
  - manual browser and curl-based smoke checks for core panel flows.
- Add focused tests only if execution reveals an uncovered production-sensitive gap, such as:
  - trusted-host regressions;
  - auth cache-control expectations;
  - provider degraded-state rendering;
  - login rate-limit behavior.

**Why**

- The repository now contains meaningful production-sensitive logic. The last step before deployment should be confidence-building, not feature chasing.

**How**

- Run the current suite first.
- If a failure appears, fix the code or test as appropriate.
- Re-run only the minimum necessary verification after each atomic fix, then finish with the full suite again.

### 4. Reconcile deployment assets with the actual production topology

**Files to inspect and possibly update**

- `scripts/check-production.sh`
- `scripts/install.sh`
- `systemd/tetra-host.service`
- `nginx/tetra-host.conf`
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS.md`
- `.env.example`

**What**

- Validate that the deployment contract in the repo matches the actual host topology:
  - Plesk/NGINX proxy in front of local `uvicorn`;
  - TLS terminated before the app;
  - correct forwarded headers;
  - correct expected environment values for production.
- If the live environment mismatch reveals missing documentation or a deployment-script blind spot, patch the repository so the next rollout is repeatable without rediscovering the issue.

**Why**

- The known blocker came from configuration drift between a hardened codebase and a still-localhost-oriented production `.env`.

**How**

- Confirm the exact production env contract:
  - `APP_ENV=production`
  - `BASE_URL=https://panel.cloud-industry.com`
  - `ALLOWED_HOSTS_RAW` including the real domain and safe loopback entries
  - `SESSION_HTTPS_ONLY=true`
  - `FORCE_HTTPS_REDIRECT=true`
- Preserve the current native deployment approach, but update docs/scripts if they do not sufficiently enforce or explain these values.

### 5. Perform the final deployment verification on the target server

**Runtime targets to verify**

- `https://panel.cloud-industry.com/health`
- `https://panel.cloud-industry.com/auth/login`
- `https://panel.cloud-industry.com/dashboard`
- authenticated access to:
  - `/sites`
  - `/mail`
  - `/dns`
  - `/admin`

**What**

- Re-run the smoke checks that were pending at interruption time.
- If the public domain is healthy after the `.env` correction, proceed with final authenticated verification and operational spot checks.
- If the public domain still fails, inspect only the minimum necessary remote state to isolate whether the problem is:
  - app-level trusted-host/session config;
  - reverse-proxy host header forwarding;
  - stale service or stale NGINX config;
  - mismatch between Plesk-managed proxy rules and repo expectations.

**Why**

- This is the final unresolved step directly blocking completion of the user request.

**How**

- Start with non-destructive `curl` checks.
- Then use browser-based smoke testing for actual login and page navigation if needed.
- Review service logs if the public behavior differs from loopback health.

## Execution Sequence

1. Read the new continuation plan and refresh current repository context.
2. Run local lint/tests/diagnostics to establish a clean baseline.
3. Audit app middleware/auth/proxy-sensitive code against current official guidance.
4. Fix any concrete issues found in auth, headers, provider degrade states, or deployment assets.
5. Re-run targeted verification after each fix, then rerun the full verification matrix.
6. Validate deployment scripts/docs against the real production environment contract.
7. Confirm or re-apply the corrected production `.env` and service state on the target host if required.
8. Run public smoke checks through `panel.cloud-industry.com`.
9. Perform authenticated production smoke testing for the main admin pages.
10. Review logs and finalize only after the live deployment is stable.

## Verification Steps

### Local verification

- Run Ruff on the application and tests.
- Run the full pytest suite.
- Run diagnostics on any edited files after substantive changes.
- Manually verify locally:
  - `/health`
  - `/ready`
  - `/auth/login`
  - unauthenticated redirect from `/dashboard`
  - authenticated dashboard and logout

### Behavioral verification

- Confirm login failures return clear errors without leaking sensitive details.
- Confirm successful login redirects only to safe local paths.
- Confirm logout invalidates the session cleanly.
- Confirm provider pages:
  - load when providers are configured;
  - render useful degraded states when providers are not configured;
  - do not crash on upstream API errors.
- Confirm any deploy or refresh action remains gated and CSRF protected.

### Production verification

- Confirm `systemctl status tetra-host --no-pager` is healthy.
- Confirm loopback health:
  - `http://127.0.0.1:8088/health`
  - `http://127.0.0.1:8088/ready`
- Confirm public-domain behavior:
  - `https://panel.cloud-industry.com/health`
  - `https://panel.cloud-industry.com/auth/login`
  - redirect behavior for unauthenticated `/dashboard`
- Confirm authenticated production navigation across dashboard, sites, mail, DNS, and admin.
- Check logs for host-header errors, session errors, provider failures, and proxy misconfiguration.

## Risks And Mitigations

- Risk: the repo is already mostly complete, so unnecessary extra features could destabilize the release.
  - Mitigation: make only verification-driven changes.
- Risk: production still differs from repo assumptions because Plesk manages part of the reverse proxy path.
  - Mitigation: treat proxy behavior as the source of truth during deployment verification and reflect fixes back into docs/config where appropriate.
- Risk: provider credentials or upstream permissions may be incomplete on the live host.
  - Mitigation: verify graceful degraded states and avoid broadening provider write operations.
- Risk: a final live fix may require both app and proxy adjustments.
  - Mitigation: isolate the failing layer first with loopback versus public-domain checks before changing anything.

## Out Of Scope For This Final Pass

- Rebuilding the control panel as an SPA
- Introducing a new CI/CD deployment platform
- Expanding to full tenant self-service or billing
- Adding broad destructive provider-management actions
- Replacing the existing native-host deployment model
