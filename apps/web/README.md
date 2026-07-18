# Tetra Host Console

The customer-facing web console for [Tetra Host](../../README.md) — a Next.js 16 (App Router) +
React 19 app styled with Tailwind CSS v4 and shadcn/ui-style primitives (New York look). It talks
exclusively to the FastAPI control plane's `/api/v1` JSON contract.

## Run it

```bash
pnpm install
cp .env.example .env.local   # point BACKEND_API_BASE_URL at a running control plane
pnpm dev                     # http://127.0.0.1:3000
```

The backend must be running (from the repo root: `uvicorn app.main:app --reload --port 8088`).
Log in with an admin account seeded by `scripts/bootstrap-admin.sh`.

## Checks

```bash
pnpm check       # lint + typecheck + vitest — run before claiming work done
pnpm test        # vitest only
pnpm build       # production build
```

## How it's put together

- `src/app/(console)/*` — authed console routes (server components fetch via `src/lib/api.ts`).
  Every segment has `loading.tsx` skeletons; `error.tsx` boundaries keep the shell alive on
  failure; provider outages surface through `src/lib/fetch-degraded.ts` + `DegradedBanner`
  instead of rendering as empty states.
- `src/app/api/proxy/[...path]` — the only browser→backend path; injects the session token
  server-side so it never reaches the client.
- `src/components/ui/*` — the design-system primitives (Radix-based, class-variance-authority
  variants, semantic status tokens). Feature components live in `src/components/<feature>/`.
- `src/lib/client-api.ts` + `src/hooks/use-action.ts` — the client-side fetch + mutation
  pattern; use these instead of hand-rolling `fetch`/pending/error state.
- Fonts, tokens, and the violet/cyan brand system live in `src/app/globals.css`.

**Heads-up:** this Next.js version has breaking changes vs. most training data/tutorials
(e.g. `error.tsx` receives `unstable_retry`, not `reset`). Read the local docs in
`node_modules/next/dist/docs/` before writing route-convention code — see `AGENTS.md`.
