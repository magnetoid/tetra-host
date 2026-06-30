## Task 1.4 Report — Migration: seed plans + ALTER tables + backfill

### Statements added (in order of execution within `_upgrade_existing_schema`)

**New guarded ALTERs (after existing Task 1.3 ALTERs):**
```sql
-- plan_id on tenants (re-inspected after status/is_platform_scope ALTERs)
ALTER TABLE tenants ADD COLUMN plan_id VARCHAR(36)

-- role on admin_users (re-inspected after tenant_id ALTER)
ALTER TABLE admin_users ADD COLUMN role VARCHAR(20) DEFAULT 'owner'
```
Both guarded with `if col not in get_columns(table)`.

**Plan seeding (`_seed_default_plans`)** — called when `plans` table exists; idempotent on `key` via `SELECT id FROM plans WHERE key = :key` before each INSERT:
- Free: max_apps=1, max_domains=0, cpu_millicores=500, mem_mb=512, disk_mb=2048, sort_order=0
- Pro: max_apps=10, max_domains=5, cpu_millicores=8000, mem_mb=8192, disk_mb=40960, sort_order=1
- Business: max_apps=50, max_domains=25, cpu_millicores=40000, mem_mb=65536, disk_mb=409600, sort_order=2

**Backfills (`_backfill_task14`)** — always executed (even on fresh DBs), each statement is idempotent:
```sql
-- Only if legacy is_active column present:
UPDATE tenants SET status='suspended' WHERE is_active = 0 AND status='active'

UPDATE tenants SET is_platform_scope=1 WHERE slug='default'

UPDATE tenants SET plan_id=(SELECT id FROM plans WHERE key='free') WHERE plan_id IS NULL

UPDATE admin_users SET role='platform_admin' WHERE lower(email)=:bootstrap_email

-- Ensure ≥1 platform_admin (fallback to oldest):
UPDATE admin_users SET role='platform_admin'
  WHERE id=(SELECT id FROM admin_users ORDER BY created_at LIMIT 1)
-- (only executed if COUNT(*) WHERE role='platform_admin' = 0)
```

### Files changed
- `app/db/session.py` — extended `_upgrade_existing_schema`, added `_seed_default_plans` and `_backfill_task14` helpers
- `tests/test_migration_tenants_plans.py` — new test file (2 tests)
- `tests/test_plans.py` — fixed `test_plan_round_trips` to not re-insert the now-seeded free plan

### Idempotency proof
`init_db()` called twice in `test_migration_is_idempotent_and_backfills` — both calls succeed with no error. On second call: all `if col not in get_columns(...)` guards skip the ALTERs; all plan `SELECT ... WHERE key=:key` checks return existing rows so no duplicate INSERTs; all UPDATE backfills are no-ops on already-correct data.

### Migration test output
```
tests/test_migration_tenants_plans.py::test_migration_is_idempotent_and_backfills PASSED
tests/test_migration_tenants_plans.py::test_default_plans_seeded PASSED
2 passed in 0.26s
```

### Full suite result
```
75 passed, 7 skipped, 2 warnings, 14 errors
```
The 14 errors are all pre-existing `attempt to write a readonly database` failures in `test_write_actions.py` (9 errors) and `test_phase2.py` (5 errors) — confirmed to pass in isolation, noted as known flake in task brief. No new failures introduced.

### ruff
```
All checks passed!
```

---

## Task 1.4 Fix Report — Bootstrap admin gets platform_admin role on first boot

### Gap fixed
On a fresh install's first boot, `_backfill_task14` ran while `admin_users` was empty (bootstrap admin inserted after `init_db` returns), so no admin had `role='platform_admin'` until second boot. This made all staff-only gating unreachable on first deploy.

### Exact line changed
`app/modules/auth/service.py` — `ensure_bootstrap_admin` constructor:
- Added import: `from app.models.admin import ROLE_PLATFORM_ADMIN`
- Added `role=ROLE_PLATFORM_ADMIN` to the `AdminUser(...)` constructor call (line ~93)

The migration's `_backfill_task14` remains intact as the safety net for legacy DBs that already exist.

### TDD test result
`tests/test_bootstrap_role.py::test_bootstrap_admin_is_platform_admin`
- RED (before fix): `AssertionError: assert 'owner' == 'platform_admin'`
- GREEN (after fix): `1 passed in 4.38s`

### Full suite result
```
90 passed, 7 skipped, 2 warnings in 93.41s
```
(Previously 89 passed; the new test adds 1. All 7 skips are pre-existing.)

### ruff (post-fix)
```
All checks passed!
```
