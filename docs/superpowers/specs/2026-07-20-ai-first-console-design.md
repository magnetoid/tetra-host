# AI-first Tetra console — design spec

Date: 2026-07-20. Status: approved (A/A/A/A + reskin: full adoption, theme-aware).

Two sub-projects, sequenced **B → A**, each shipped as its own PR(s):

- **B — Console editorial reskin** (frontend only). Adopt the approved artifact look:
  editorial, hairline/divider layout, mono-forward, top-bar + top-tabs, theme-aware
  light(default)+dark.
- **A — AI-first agentic assistant.** A persistent, tenant-scoped side-panel agent on a
  shared tool-core, read-free / writes-confirmed, powered by the metered OpenRouter
  gateway (Claude default).

---

## B — Console editorial reskin

### Reference
`scratchpad/tetra-dashboard-reference.png` (rendered from the approved artifact).

### Design system (`apps/web/src/app/globals.css`)
Flip the default theme to a **warm-light editorial** palette; keep dark as `[data-theme="dark"]`.
- Light (default `:root`): canvas `#faf9f5`, ink `#1a1a1a`, hairline `#e6e4dd`, accent violet
  `#6366f1`; status green `#10b981` / teal `#14b8a6` / red `#ef4444` / amber `#f59e0b`.
- Dark: carry the same structure over the existing near-black surfaces (nothing regresses).
- Theme mechanics: `lib/theme.ts` default becomes **light**; `applyTheme`/cookie already set
  `data-theme` explicitly, so only the fallback + the `:root`/`[data-theme=*]` blocks move.
- Numerics: JetBrains/Geist Mono for all KPIs, hashes, durations, log lines (utility/class).

### Shell (`components/shell/app-shell.tsx`, `lib/navigation.ts`)
Replace the left sidebar with:
- **Top bar**: brand mark + wordmark · tenant switcher · role badge (PLATFORM) · ⌘K search ·
  live build-status chip · user menu.
- **Underline top-tabs**: Overview / Projects / Databases / DNS / Mail / Servers / Admin /
  Account (regroup `consoleNavItems` from sidebar-sections into a flat tab list; keep
  `platformAdminOnly`). Per-app secondary nav (deployments/logs/env/…) stays as an in-project
  row (reuse `projectNavItems`).
- Command palette (⌘K) and View Transitions are retained.

### Overview dashboard (`app/(console)/dashboard/page.tsx`)
- **KPI rail**: 6 columns divided by vertical hairlines (no cards): Projects, Deploys/24h,
  Uptime 30d, DNS zones, Mailboxes, MRR — big mono numbers + uppercase micro-label + colored
  sub-line. New `components/dashboard/kpi-rail.tsx`.
- **Left column**: Deployments table (reuse `components/ui/data-table.tsx`) — status dot ·
  app·tenant · commit+message · status · duration · relative time; below it a live
  **build-log console** panel (`components/dashboard/build-log.tsx`).
- **Right rail**: 30-day uptime bar chart (Tremor), resource-quota progress bars, Providers
  health list, Billing summary. New `components/dashboard/right-rail/*`.
- Data from existing endpoints (deploys, uptime monitors, quota/usage, provider health,
  billing). **No backend changes.**

### Reuse / new
Reuse: Tremor charts, `data-table`, brand marks, `fetchDegraded`, status tokens. New focused
components listed above; restyle `stat-card` into the divider KPI form.

### Testing
`pnpm web:check` green; vitest for new components; browser-drive a **prod build in light+dark**
and screenshot against the reference; then console deploy flow.

---

## A — AI-first agentic assistant (spec'd in detail after B ships)

### Shared agent tool-core (`app/services/agent/`)
Extract the MCP tool registry (`tetra_cli/mcp.py`) into a provider-agnostic **tool catalog +
executor**: each tool = name, JSON schema, read|write class, tenant-scoped handler over the
`/api/v1` service layer. The MCP server, the CLI, and the assistant all consume this one
catalog (parity is structural, not duplicated). Tenant-scoped catalog **excludes**
platform-admin/billable ops + DNS writes (mirrors current MCP exclusions).

### Agent runtime + API
`AssistantService` runs the tool-calling loop against OpenRouter (Claude default model,
user-swappable), metered via `AiResellerService`. **Reads execute immediately; writes are
returned as proposed actions** (never executed by the loop) that the user approves. Streaming
over SSE: `POST /api/v1/assistant/messages` (stream tokens + tool events + proposed actions),
`POST /api/v1/assistant/actions/{id}/approve|reject`. Every tool call audited. Tenant isolation
enforced server-side — never trust model-supplied tenant/ids.

### Console surface
Persistent dockable **side panel** (⌘J) on every console page, context-aware (passes current
route/app). Renders streamed text, a tool-call timeline, and proposed-action cards with
Approve / Edit / Cancel.

### Parity + tests
CLI gains an `tetra assistant`/agent equivalent; MCP unchanged (already the same catalog).
Tests: tool-core unit tests, agent loop with a mock LLM, approval-gating, tenant isolation,
SSE endpoint, console panel component.

---

## Non-goals (v1)
- No full-autonomous writes (writes always confirmed).
- No platform-admin agent (tenant self-service only).
- No conversation training/memory beyond a session transcript.
