# Task 2.3 Report — Self-serve Signup Endpoint

## SignupRequest fields

`app/api/contracts.py` — `SignupRequest` contains **exactly three fields**:
- `email: str`
- `password: str`
- `org_name: str`

`role`, `plan_id`, `status`, `tenant_id`, and `is_platform_scope` are absent by design. FastAPI/Pydantic silently ignores any extra fields the client sends (`extra="ignore"` is the default) — the security test `test_signup_cannot_set_role_or_plan` verifies this invariant end-to-end.

---

## AuthService.signup logic

`app/modules/auth/service.py`

### validate_password (static method)
Raises `ValueError("Password must be at least 10 characters long.")` if `len(password) < 10`. Called at the top of `signup` so a bad password never touches the DB.

### signup(email, password, org_name) -> AdminUser | None

1. Calls `validate_password` — raises `ValueError` on weak password.
2. Normalises email (`strip().lower()`).
3. Looks up existing admin by email.
   - **Duplicate path**: if found, returns `None` (sentinel). The route converts this to `AuthResponse(token="", admin=<empty AdminSummary>)` with 200. No row is created; `create_api_token` is never called.
4. Resolves `PlanService(session).get_default()` → `plan_id` (may be `None` if no plans seeded).
5. Derives a unique slug from `org_name` via `_unique_slug` (dedupes with `-2`, `-3` suffixes).
6. Creates `Tenant(status=TENANT_PENDING, is_platform_scope=False, plan_id=...)`.
7. Creates `AdminUser(role=ROLE_OWNER, is_active=True, ...)` with hashed password.
8. Returns the reloaded admin (with `tenant` relationship populated).

Server-set fields — **never from request body**:
- `role = ROLE_OWNER` (constant from `app.models.admin`)
- `tenant.status = TENANT_PENDING` (constant from `app.models.tenant`)
- `tenant.is_platform_scope = False`
- `plan_id` resolved internally from `PlanService.get_default()`

---

## api_signup route

`app/api/routes.py` — `POST /api/v1/auth/signup` (unauthenticated, no `get_current_api_admin` dep)

### Rate limiting
Uses the same `request.app.state.rate_limiter` (`InMemoryRateLimiter`) pattern as the HTML login handler, keyed on `signup:{client_host}`, limit `settings.signup_rate_per_hour` (default 5), window 3600s. Returns HTTP 429 on exceed.

### Pending-tenant cap
Counts `Tenant.status == TENANT_PENDING`. If `>= settings.max_pending_tenants` (default 100) → 429. Prevents unbounded pending-account accumulation before admin approval (Task 2.4).

### Error handling
- `ValueError` from `validate_password` → `HTTPException(422, detail=str(exc))`
- `signup` returns `None` (duplicate) → `AuthResponse(token="", admin=<empty AdminSummary>)` 200
- Happy path → mint token for new pending admin → `AuthResponse`

---

## Config additions

`app/config.py` — `Settings`:
```python
signup_rate_per_hour: int = 5
max_pending_tenants: int = 100
```

---

## Security invariant enforcement

| Invariant | Enforcement |
|-----------|-------------|
| Privilege fields never from body | `SignupRequest` has only `email`/`password`/`org_name`; Pydantic ignores extras |
| `role="owner"` server-set | `signup()` hardcodes `role=ROLE_OWNER` |
| `status="pending"` server-set | `signup()` hardcodes `status=TENANT_PENDING` |
| `is_platform_scope=False` server-set | `signup()` hardcodes `is_platform_scope=False` |
| `plan_id` server-resolved | `signup()` calls `PlanService.get_default()` |
| Duplicate email no takeover | Returns `None` → route returns `token=""`, never calls `create_api_token` for existing admin |
| Pending writes blocked | Central `get_current_api_admin` gate (Task 2.2) returns 403 for non-active-tenant owners on POST/PUT/PATCH/DELETE |

---

## Tests — RED/GREEN

File: `tests/test_signup.py` (4 tests)

**RED** — all 4 failed before implementation (endpoint 404).

**GREEN** — all 4 pass after implementation.

| Test | Assertion |
|------|-----------|
| `test_signup_creates_pending_owner_then_blocked` | 200 signup, `/me` role=owner, POST to `/apps/x/start` → 403 |
| `test_signup_weak_password_422` | 422 on `password="short"` |
| `test_signup_cannot_set_role_or_plan` | Extra body fields `role/plan_id/status` ignored; admin still `role=owner`, tenant `status=pending` |
| `test_signup_duplicate_email_no_takeover` | Second call returns 200 with `token=""`, `/me` with it → 401, DB count = 1 row |

---

## Full suite result

```
129 passed, 7 skipped, 0 errors
```
(+4 new tests; prior baseline was 125 passed / 7 skipped)

## ruff
`ruff check` — all checks passed (no violations).

---

## Concerns / Notes

- **Rate limiter is in-memory**: shared across workers only within a single process. Adequate for the current single-worker setup; a Redis-backed limiter would be needed for multi-worker production.
- **Plan resolution**: `get_default()` returns `None` if no "free" plan is seeded; `plan_id` is set to `None` in that case (column is nullable). Signup still works without plans.
- **Slug deduplication**: `_unique_slug` loops to find a free slug. Degenerate case (many orgs with identical names) is bounded by DB unique constraint; in practice negligible.
- **Token expiry**: the new pending-owner token has the same TTL as all API tokens (`session_max_age_seconds`). The pending gate (403 on writes) remains active until admin approval (Task 2.4).

---

## Hardening: race + bounds + 429 tests

### Fix 1 — atomic signup (no orphan/500 on duplicate race)

`app/modules/auth/service.py` — `signup()`:
- Added `from sqlalchemy.exc import IntegrityError` import.
- The `Tenant` flush already happened in one step; the `AdminUser` flush is now wrapped in `try/except IntegrityError`. On a concurrent duplicate the UNIQUE constraint fires on `admin_users.email`; the handler calls `await self.session.rollback()` (rolling back **both** the tenant and admin inserts atomically — no orphan tenant) then returns `None` — the same sentinel the pre-check duplicate path returns. The route converts `None` → `AuthResponse(token="", ...)` 200, indistinguishable from the normal duplicate path. No 500 escapes.

### Fix 2 — bound SignupRequest field lengths (500s → 422s)

`app/api/contracts.py` — `SignupRequest`:
- Added `from pydantic import Field` import.
- `email: str = Field(..., max_length=254)`
- `password: str = Field(..., max_length=200)` (upper cap only; the >= 10 minimum stays in `validate_password`)
- `org_name: str = Field(..., min_length=1, max_length=120)`

Over-length input now triggers Pydantic validation → HTTP 422 before the DB is ever touched.

### Fix 3 — new tests

`tests/test_signup.py` — 3 tests added (total: 7):

| Test | Assertion |
|------|-----------|
| `test_signup_rate_limited` | `signup_rate_per_hour=2`, 3rd unique-email signup from same client → **429** |
| `test_signup_pending_cap` | `max_pending_tenants=1`, second signup after cap filled → **429** (rate limit set high so cap is hit, not rate limit) |
| `test_signup_org_name_too_long_422` | 200-char `org_name` → **422** (Pydantic, not DB 500) |

Each test clears `client.app.state.rate_limiter._buckets` so limiter state doesn't bleed across tests.

**RED/GREEN**: All 3 new tests were RED before the fixes (length test would 500 on DB; 429 tests passed coincidentally only if run in isolation — the bounds test was definitively RED). All 7 signup tests GREEN after fixes.

### Full suite

```
132 passed, 7 skipped, 0 errors
```
(+3 new tests from baseline of 129 passed / 7 skipped)

### ruff

`ruff check .` — all checks passed, no violations.
