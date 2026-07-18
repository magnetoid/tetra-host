# Contributing to Tetra Host

## Setup

Follow the "Run it locally" section of the [README](README.md) — backend venv + `pip install
-e ".[dev]"`, console `pnpm install`. No provider credentials are needed for development or
tests.

## Before you open a PR

Run the same checks CI runs:

```bash
ruff check .        # backend lint (line length 100)
pytest              # backend tests
pnpm web:check      # console lint + typecheck + vitest
```

## Ground rules

- **Thin handlers, fat services.** Route handlers stay thin; provider and domain logic lives in
  `app/modules/*/service.py` / `app/services/*`. Provider HTTP goes through
  `app/services/http.py` (`request_json`) and surfaces `ProviderAPIError`.
- **Features are plugins.** New capability = new module under `app/modules/<name>/` registered
  in `load_plugins()` — don't grow `app/main.py` or bolt routes onto unrelated modules.
- **Parity is a charter rule.** A dashboard feature ships with the matching `tetra` CLI command
  (and, where safe, MCP exposure). The console, CLI, and MCP all consume the same `/api/v1`
  contract typed in `app/api/contracts.py`.
- **Multi-tenancy is mandatory.** Data access, API responses, and admin behavior isolate by
  tenant; platform-global shortcuts are debt.
- **Console conventions.** Server components fetch via `lib/api.ts` / `lib/fetch-degraded.ts`
  (never swallow provider failures silently); client mutations use `hooks/use-action.ts` +
  `lib/client-api.ts`; primitives live in `components/ui/*`. This Next.js version has breaking
  changes vs. tutorials — check `node_modules/next/dist/docs/` first (see `apps/web/AGENTS.md`).
- **Tests ride along.** Behavioral changes come with pytest coverage (backend) or vitest
  component tests (console). CSRF-protected form flows have a helper:
  `extract_csrf_token(html)` in `tests/conftest.py`.
- **Keep intent docs true.** If you change architecture, update `.torsor/` (and `CLAUDE.md`
  where relevant) in the same PR.
