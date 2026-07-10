# Per-Project Sub-Nav Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a Vercel-style per-project nested layout with a left sub-nav (Overview / Deployments / Logs / Env / Domains / Metrics / Errors / Settings), reorganizing the existing monolithic project detail page into separate sub-routes.

**Architecture:** Create a `layout.tsx` under `apps/web/src/app/(console)/projects/[id]/` that wraps all sub-pages with a client-side `ProjectSubNav` component. Each section becomes its own `page.tsx` sub-route that reuses existing client components (`DeployConsole`, `LogStream`, `EnvManager`, `ProjectActions`) — no logic is re-implemented. The layout fetches the project name server-side (for the sub-nav header) and passes the project `id` to the client sub-nav so it can build active-state-aware links.

**Tech Stack:** Next.js 16 app-router nested layouts, React 19 server + client components, shadcn/ui (`Card`, `CardHeader`, `EmptyState`), Font Awesome icons (`@/lib/icons`), `usePathname` for active-link detection, vitest + @testing-library/react for the sub-nav smoke test.

## Global Constraints

- shadcn/ui + Font Awesome only (no lucide icons; `FontAwesomeIcon` from `@fortawesome/react-fontawesome`).
- Icons must be imported from `@/lib/icons` (the project's curated re-export). Any FA icon not yet in `icons.ts` must be added there first.
- `params` is `Promise<{ id: string }>` (Next 15/16 async params — always `await params`).
- No new npm dependencies.
- `"use client"` only on components that use hooks or browser APIs; layouts and pages are server components by default.
- Do not regress existing `pnpm web:check` (lint + typecheck + vitest) green status.
- Each sub-page fetches only what it needs (no over-fetching from the parent layout).
- The parent `(console)/layout.tsx` (`AppShell`) must not be changed.
- Report destination: `/Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host/.superpowers/sdd/task-r3b-report.md`
- Commit branch: `feat/post-deploy-followups` (already exists and checked out).
- Git-ignore report file — do NOT `git add` it.

---

## File Map

Files to **create**:
- `apps/web/src/app/(console)/projects/[id]/layout.tsx` — Server component. Fetches project name; renders two-column layout with `<ProjectSubNav>` (left) and `{children}` (right).
- `apps/web/src/components/projects/project-sub-nav.tsx` — `"use client"`. Renders the 8-section sub-nav; uses `usePathname` for active detection. Accepts `{ id: string; projectName: string }`.
- `apps/web/src/app/(console)/projects/[id]/deployments/page.tsx` — Server page for Deployments section.
- `apps/web/src/app/(console)/projects/[id]/logs/page.tsx` — Server page for Logs section.
- `apps/web/src/app/(console)/projects/[id]/env/page.tsx` — Server page for Env section.
- `apps/web/src/app/(console)/projects/[id]/domains/page.tsx` — Server page for Domains section.
- `apps/web/src/app/(console)/projects/[id]/metrics/page.tsx` — Stub server page for Metrics.
- `apps/web/src/app/(console)/projects/[id]/errors/page.tsx` — Stub server page for Errors.
- `apps/web/src/app/(console)/projects/[id]/settings/page.tsx` — Server page for Settings section.
- `apps/web/src/components/projects/project-sub-nav.test.tsx` — Vitest smoke test for the sub-nav.

Files to **modify**:
- `apps/web/src/app/(console)/projects/[id]/page.tsx` — Slim to Overview-only (status badge strip + latest deployment summary). Remove `DeployConsole` and `EnvManager` (moved to sub-pages).
- `apps/web/src/lib/icons.ts` — Add any missing FA icons needed by sub-nav items.

---

## Task 1: Add Required Icons to `icons.ts`

**Files:**
- Modify: `apps/web/src/lib/icons.ts`

**Interfaces:**
- Consumes: nothing
- Produces: `faListCheck`, `faTerminal`, `faKey`, `faEarthAmericas`, `faChartLine`, `faBug`, `faGear` — exported from `@/lib/icons`.

The sub-nav needs icons not currently in `icons.ts`:
- `faListCheck` (Deployments) — available in `@fortawesome/free-solid-svg-icons`
- `faTerminal` (Logs) — available in `@fortawesome/free-solid-svg-icons`
- `faKey` (Env) — available in `@fortawesome/free-solid-svg-icons`
- `faEarthAmericas` (Domains) — available in `@fortawesome/free-solid-svg-icons`
- `faChartLine` (Metrics) — available in `@fortawesome/free-solid-svg-icons`
- `faBug` (Errors) — available in `@fortawesome/free-solid-svg-icons`
- `faGear` (Settings) — available in `@fortawesome/free-solid-svg-icons`
- `faTableColumns` (Overview) — available in `@fortawesome/free-solid-svg-icons`

- [ ] **Step 1: Open `apps/web/src/lib/icons.ts` and add the missing icons**

Replace the import block with an expanded one:

```typescript
/**
 * Central icon registry — Font Awesome. Import icons from here (not directly from the FA
 * packages) so the whole console shares one consistent, curated icon set.
 */
import { faGithub } from "@fortawesome/free-brands-svg-icons"
import {
  faArrowRightFromBracket,
  faArrowsRotate,
  faArrowUpRightFromSquare,
  faBan,
  faBox,
  faBug,
  faChartBar,
  faChartLine,
  faCircleCheck,
  faCircleExclamation,
  faCirclePlay,
  faCircleStop,
  faCloud,
  faEarthAmericas,
  faEnvelope,
  faGaugeHigh,
  faGear,
  faGlobe,
  faHourglassHalf,
  faKey,
  faLayerGroup,
  faListCheck,
  faMagnifyingGlass,
  faPlus,
  faRocket,
  faServer,
  faSliders,
  faTableColumns,
  faTerminal,
  faTrash,
  faTriangleExclamation,
  faUsers,
  faUserShield,
} from "@fortawesome/free-solid-svg-icons"

export {
  faArrowRightFromBracket,
  faArrowsRotate,
  faArrowUpRightFromSquare,
  faBan,
  faBox,
  faBug,
  faChartBar,
  faChartLine,
  faCircleCheck,
  faCircleExclamation,
  faCirclePlay,
  faCircleStop,
  faCloud,
  faEarthAmericas,
  faEnvelope,
  faGaugeHigh,
  faGear,
  faGithub,
  faGlobe,
  faHourglassHalf,
  faKey,
  faLayerGroup,
  faListCheck,
  faMagnifyingGlass,
  faPlus,
  faRocket,
  faServer,
  faSliders,
  faTableColumns,
  faTerminal,
  faTrash,
  faTriangleExclamation,
  faUsers,
  faUserShield,
}
```

- [ ] **Step 2: Verify no typecheck errors**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web typecheck
```

Expected: exits 0 (no errors relating to icon imports).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/icons.ts
git commit -m "feat(console): add FA icons for per-project sub-nav items"
```

---

## Task 2: Create `ProjectSubNav` Client Component

**Files:**
- Create: `apps/web/src/components/projects/project-sub-nav.tsx`

**Interfaces:**
- Consumes: FA icons from `@/lib/icons` (Task 1), `usePathname` from `next/navigation`, `Link` from `next/link`, `FontAwesomeIcon` from `@fortawesome/react-fontawesome`, `cn` from `@/lib/utils`.
- Produces: `export function ProjectSubNav({ id, projectName }: { id: string; projectName: string }): JSX.Element` — used by the layout in Task 3.

The component renders the left sub-nav. Active detection: a section is "active" when `pathname === href` (exact match for Overview, which is `/projects/${id}`) or `pathname.startsWith(href + "/")` for all others. This prevents `/projects/[id]` from also highlighting when on `/projects/[id]/deployments`.

- [ ] **Step 1: Write the failing test first** (see Task 8 for the full test — write the test file now so the import fails, confirming the component doesn't exist yet)

```bash
cat > /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host/apps/web/src/components/projects/project-sub-nav.test.tsx << 'EOF'
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

// Mock next/navigation before importing the component
vi.mock("next/navigation", () => ({ usePathname: vi.fn() }))
// Mock next/link to render a plain <a>
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

import { usePathname } from "next/navigation"
import { ProjectSubNav } from "@/components/projects/project-sub-nav"

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

describe("ProjectSubNav", () => {
  it("renders all eight section links", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/abc123")
    render(<ProjectSubNav id="abc123" projectName="My App" />)
    expect(screen.getByText("Overview")).toBeInTheDocument()
    expect(screen.getByText("Deployments")).toBeInTheDocument()
    expect(screen.getByText("Logs")).toBeInTheDocument()
    expect(screen.getByText("Env")).toBeInTheDocument()
    expect(screen.getByText("Domains")).toBeInTheDocument()
    expect(screen.getByText("Metrics")).toBeInTheDocument()
    expect(screen.getByText("Errors")).toBeInTheDocument()
    expect(screen.getByText("Settings")).toBeInTheDocument()
  })

  it("marks Overview as active on the project root path", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/abc123")
    render(<ProjectSubNav id="abc123" projectName="My App" />)
    const overviewLink = screen.getByRole("link", { name: /overview/i })
    expect(overviewLink).toHaveAttribute("href", "/projects/abc123")
    expect(overviewLink.className).toMatch(/bg-zinc-800|text-white/)
  })

  it("marks Deployments as active on the deployments path", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/abc123/deployments")
    render(<ProjectSubNav id="abc123" projectName="My App" />)
    const deployLink = screen.getByRole("link", { name: /deployments/i })
    expect(deployLink.className).toMatch(/bg-zinc-800|text-white/)
    // Overview must NOT be active
    const overviewLink = screen.getByRole("link", { name: /overview/i })
    expect(overviewLink.className).not.toMatch(/bg-zinc-800/)
  })

  it("renders the project name as the nav header", () => {
    vi.mocked(usePathname).mockReturnValue("/projects/abc123")
    render(<ProjectSubNav id="abc123" projectName="Acme Blog" />)
    expect(screen.getByText("Acme Blog")).toBeInTheDocument()
  })
})
EOF
```

- [ ] **Step 2: Run test to confirm it fails** (component not yet created)

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web test -- --reporter=verbose project-sub-nav.test 2>&1 | tail -20
```

Expected: FAIL — "Cannot find module '@/components/projects/project-sub-nav'"

- [ ] **Step 3: Create `project-sub-nav.tsx`**

```typescript
"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { usePathname } from "next/navigation"

import {
  faBug,
  faChartLine,
  faEarthAmericas,
  faGear,
  faKey,
  faListCheck,
  faTableColumns,
  faTerminal,
} from "@/lib/icons"
import { cn } from "@/lib/utils"
import type { IconDefinition } from "@fortawesome/fontawesome-svg-core"

type SubNavItem = {
  href: string
  label: string
  icon: IconDefinition
  /** If true, only `/projects/[id]` exactly activates this item. */
  exact?: boolean
}

function buildNavItems(id: string): SubNavItem[] {
  return [
    { href: `/projects/${id}`, label: "Overview", icon: faTableColumns, exact: true },
    { href: `/projects/${id}/deployments`, label: "Deployments", icon: faListCheck },
    { href: `/projects/${id}/logs`, label: "Logs", icon: faTerminal },
    { href: `/projects/${id}/env`, label: "Env", icon: faKey },
    { href: `/projects/${id}/domains`, label: "Domains", icon: faEarthAmericas },
    { href: `/projects/${id}/metrics`, label: "Metrics", icon: faChartLine },
    { href: `/projects/${id}/errors`, label: "Errors", icon: faBug },
    { href: `/projects/${id}/settings`, label: "Settings", icon: faGear },
  ]
}

function SubNavLink({ item, active }: { item: SubNavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-white",
        active && "bg-zinc-800 text-white",
      )}
    >
      <FontAwesomeIcon
        icon={item.icon}
        className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-zinc-500")}
        fixedWidth
      />
      {item.label}
    </Link>
  )
}

export function ProjectSubNav({
  id,
  projectName,
}: {
  id: string
  projectName: string
}) {
  const pathname = usePathname()
  const items = buildNavItems(id)

  return (
    <nav className="flex flex-col gap-1">
      {/* Project header */}
      <div className="mb-4 px-3">
        <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">Project</div>
        <div className="mt-1 truncate text-sm font-semibold text-zinc-100">{projectName}</div>
      </div>

      {items.map((item) => {
        const active = item.exact
          ? pathname === item.href
          : pathname === item.href || pathname.startsWith(`${item.href}/`)
        return <SubNavLink key={item.href} item={item} active={active} />
      })}
    </nav>
  )
}
```

- [ ] **Step 4: Run the test — must pass**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web test -- --reporter=verbose project-sub-nav.test 2>&1 | tail -30
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/projects/project-sub-nav.tsx apps/web/src/components/projects/project-sub-nav.test.tsx
git commit -m "feat(console): add ProjectSubNav client component with active-state detection and smoke tests"
```

---

## Task 3: Create the Per-Project Nested Layout

**Files:**
- Create: `apps/web/src/app/(console)/projects/[id]/layout.tsx`

**Interfaces:**
- Consumes: `ProjectSubNav` from Task 2, `fetchBackend` from `@/lib/api`, `requireConsoleSession` from `@/lib/auth`, `ProjectRecord` from `@/lib/types`.
- Produces: `ProjectLayout` — wraps all `projects/[id]/*` sub-pages with a two-column (sub-nav + main content) layout. The outer `(console)/layout.tsx` (`AppShell`) remains untouched and continues to wrap this layout.

The layout fetches the project list (same call pattern as `projects/page.tsx`) to get the project name for the sub-nav header. It renders: a narrow left column (the sub-nav), a `<main>` right column (children). If the project is not found it falls through — sub-pages handle `notFound()` individually.

Key Next 15/16 API: `params` is `Promise<{ id: string }>`, so the layout must be `async` and `await params`.

- [ ] **Step 1: Create `layout.tsx`**

```typescript
import { notFound } from "next/navigation"

import { ProjectSubNav } from "@/components/projects/project-sub-nav"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type ProjectLayoutProps = {
  children: React.ReactNode
  params: Promise<{ id: string }>
}

export default async function ProjectLayout({ children, params }: ProjectLayoutProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", { token: session.token })
  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="flex min-h-0 gap-8">
      {/* Per-project left sub-nav */}
      <aside className="hidden w-52 shrink-0 lg:block">
        <ProjectSubNav id={id} projectName={project.name} />
      </aside>

      {/* Section content */}
      <div className="min-w-0 flex-1">
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web typecheck 2>&1 | tail -20
```

Expected: exits 0 (no errors in the new layout).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/\(console\)/projects/\[id\]/layout.tsx
git commit -m "feat(console): add per-project nested layout with two-column sub-nav shell"
```

---

## Task 4: Rewrite Overview `page.tsx` (slim summary)

**Files:**
- Modify: `apps/web/src/app/(console)/projects/[id]/page.tsx`

**Interfaces:**
- Consumes: `fetchBackend`, `requireConsoleSession`, `ProjectRecord`, `ProjectDeploymentRecord`, `StatusBadge`, `PageHeader` — all already imported.
- Produces: Overview page — status badges + primary domain + latest deployment summary card. The `DeployConsole` and `EnvManager` sections are removed (they move to sub-pages); replaced with a brief "latest deployment" strip and a call-to-action row with links to Deployments / Env sub-pages.

The layout above now provides the left sub-nav, so the old "Back to projects" link and the monolithic page structure are replaced with a focused overview.

- [ ] **Step 1: Replace `apps/web/src/app/(console)/projects/[id]/page.tsx`**

```typescript
import Link from "next/link"
import { notFound } from "next/navigation"

import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"
import { formatRelativeLabel } from "@/lib/utils"

type ProjectDetailPageProps = {
  params: Promise<{ id: string }>
}

export default async function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, deployments] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
  ])

  const project = projects.find((item) => item.id === id)
  if (!project) {
    notFound()
  }

  const latest = deployments[0] ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Project overview"
        title={project.name}
        description="Status, domain, and latest deployment at a glance."
      />

      {/* Status strip */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <StatusBadge value={project.environment || "Production"} />
        <StatusBadge value={project.status} />
        <a
          className="text-zinc-400 hover:text-zinc-200"
          href={`https://${project.primary_domain}`}
          target="_blank"
          rel="noreferrer"
        >
          {project.primary_domain}
        </a>
        {project.repository ? (
          <span className="text-zinc-600">· {project.repository}</span>
        ) : null}
      </div>

      {/* Latest deployment card */}
      {latest ? (
        <div className="rounded-2xl border border-border bg-zinc-950/70 p-5">
          <h2 className="mb-3 text-sm font-medium text-zinc-400">Latest deployment</h2>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-zinc-400">
                {latest.commit ? latest.commit.slice(0, 7) : latest.id.slice(0, 7)}
              </span>
              <StatusBadge value={latest.status} />
              {latest.branch ? (
                <span className="text-zinc-500">{latest.branch}</span>
              ) : null}
            </div>
            <span className="text-zinc-500">{formatRelativeLabel(latest.created_at)}</span>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border p-5 text-sm text-zinc-500">
          No deployments yet — trigger one from the{" "}
          <Link href={`/projects/${id}/deployments`} className="text-zinc-300 underline underline-offset-2 hover:text-white">
            Deployments
          </Link>{" "}
          tab.
        </div>
      )}

      {/* Quick-access links */}
      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href={`/projects/${id}/deployments`}
          className="rounded-lg border border-border px-4 py-2 text-zinc-300 transition hover:bg-zinc-900"
        >
          Open deploy console →
        </Link>
        <Link
          href={`/projects/${id}/env`}
          className="rounded-lg border border-border px-4 py-2 text-zinc-300 transition hover:bg-zinc-900"
        >
          Manage env vars →
        </Link>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web typecheck 2>&1 | tail -20
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/\(console\)/projects/\[id\]/page.tsx
git commit -m "feat(console): slim project overview to status + latest-deployment summary card"
```

---

## Task 5: Create Deployments and Logs Sub-Pages

**Files:**
- Create: `apps/web/src/app/(console)/projects/[id]/deployments/page.tsx`
- Create: `apps/web/src/app/(console)/projects/[id]/logs/page.tsx`

**Interfaces:**
- Consumes (deployments page): `DeployConsole` from `@/components/projects/deploy-console`, `fetchBackend`, `requireConsoleSession`, `ProjectDeploymentRecord`, `PageHeader`.
- Consumes (logs page): `DeployConsole` from `@/components/projects/deploy-console` — the `DeployConsole` component already embeds `LogStream` and lets the user pick a deployment to view its logs. Using `DeployConsole` is correct because it covers the full "select deployment → stream logs" UX. The Logs sub-page is therefore the same component but framed as "Build logs" rather than the full deploy-console experience. Alternatively we can surface `LogStream` directly if the latest deployment id is known. **Use `DeployConsole`** — it already handles both the selection and streaming.
- Produces: two routable pages at `/projects/[id]/deployments` and `/projects/[id]/logs`.

Note: The deployments page and the logs page both use `DeployConsole` because that component already bundles a deployment-list sidebar + log stream pane. The difference is framing (headings/eyebrows). This is intentional — `LogStream` alone requires a pre-selected `deploymentId` from outside, so it's used only inside `DeployConsole` where a deployment is already selected. If the future needs pure log-only UX with a pre-picked deployment, that's a later iteration.

- [ ] **Step 1: Create `deployments/page.tsx`**

```typescript
import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"

type DeploymentsPageProps = {
  params: Promise<{ id: string }>
}

export default async function DeploymentsPage({ params }: DeploymentsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, deployments] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
  ])

  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Coolify deploy console"
        title="Deployments"
        description="Trigger deploys and watch the build stream in real time."
      />
      <DeployConsole applicationId={id} initialDeployments={deployments} />
    </div>
  )
}
```

- [ ] **Step 2: Create `logs/page.tsx`**

```typescript
import { notFound } from "next/navigation"

import { DeployConsole } from "@/components/projects/deploy-console"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectDeploymentRecord, ProjectRecord } from "@/lib/types"

type LogsPageProps = {
  params: Promise<{ id: string }>
}

export default async function LogsPage({ params }: LogsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, deployments] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<ProjectDeploymentRecord[]>(`/projects/${id}/deployments`, {
      token: session.token,
    }).catch(() => [] as ProjectDeploymentRecord[]),
  ])

  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Build output"
        title="Logs"
        description="Select a deployment from the list to stream its build log output."
      />
      <DeployConsole applicationId={id} initialDeployments={deployments} />
    </div>
  )
}
```

- [ ] **Step 3: Run typecheck**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web typecheck 2>&1 | tail -20
```

Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/\(console\)/projects/\[id\]/deployments/page.tsx apps/web/src/app/\(console\)/projects/\[id\]/logs/page.tsx
git commit -m "feat(console): add Deployments and Logs sub-pages (reuse DeployConsole)"
```

---

## Task 6: Create Env, Domains, and Settings Sub-Pages

**Files:**
- Create: `apps/web/src/app/(console)/projects/[id]/env/page.tsx`
- Create: `apps/web/src/app/(console)/projects/[id]/domains/page.tsx`
- Create: `apps/web/src/app/(console)/projects/[id]/settings/page.tsx`

**Interfaces:**
- Consumes (env): `EnvManager`, `EnvVar` from `@/components/projects/env-manager`.
- Consumes (domains): `StatusBadge`, `PageHeader`, `ProjectRecord`.
- Consumes (settings): `ProjectActions` from `@/components/projects/project-actions`.
- Produces: three routable pages.

For Domains: there is no `/api/v1/projects/{id}/domains` endpoint. Show the project's `primary_domain` (from the project record) plus an external link to the DNS zone page. Keep it simple — don't invent a backend route.

- [ ] **Step 1: Create `env/page.tsx`**

```typescript
import { notFound } from "next/navigation"

import { EnvManager, type EnvVar } from "@/components/projects/env-manager"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type EnvPageProps = {
  params: Promise<{ id: string }>
}

export default async function EnvPage({ params }: EnvPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const [projects, envs] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }),
    fetchBackend<EnvVar[]>(`/projects/${id}/envs`, { token: session.token }).catch(
      () => [] as EnvVar[],
    ),
  ])

  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Project configuration"
        title="Environment Variables"
        description="Manage runtime environment variables for this application."
      />
      <EnvManager applicationId={id} initialEnvs={envs} />
    </div>
  )
}
```

- [ ] **Step 2: Create `domains/page.tsx`**

```typescript
import Link from "next/link"
import { notFound } from "next/navigation"

import { PageHeader } from "@/components/ui/page-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type DomainsPageProps = {
  params: Promise<{ id: string }>
}

export default async function DomainsPage({ params }: DomainsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", { token: session.token })
  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Project networking"
        title="Domains"
        description="The domain(s) attached to this application."
      />

      <div className="rounded-2xl border border-border bg-zinc-950/70 p-5">
        <h2 className="mb-4 text-sm font-medium text-zinc-400">Primary domain</h2>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <StatusBadge value={project.status} />
            <a
              className="font-mono text-sm text-zinc-200 hover:text-white"
              href={`https://${project.primary_domain}`}
              target="_blank"
              rel="noreferrer"
            >
              {project.primary_domain}
            </a>
          </div>
          <Link
            href="/dns"
            className="rounded-lg border border-border px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
          >
            Manage DNS records →
          </Link>
        </div>
        <p className="mt-4 text-xs text-zinc-500">
          DNS records for this domain are managed globally via the{" "}
          <Link href="/dns" className="underline underline-offset-2 hover:text-zinc-300">
            DNS section
          </Link>
          . Additional custom domains can be configured in Coolify directly.
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `settings/page.tsx`**

```typescript
import { notFound } from "next/navigation"

import { ProjectActions } from "@/components/projects/project-actions"
import { PageHeader } from "@/components/ui/page-header"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import type { ProjectRecord } from "@/lib/types"

type SettingsPageProps = {
  params: Promise<{ id: string }>
}

export default async function SettingsPage({ params }: SettingsPageProps) {
  const session = await requireConsoleSession()
  const { id } = await params

  const projects = await fetchBackend<ProjectRecord[]>("/projects", { token: session.token })
  const project = projects.find((p) => p.id === id)
  if (!project) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Project management"
        title="Settings"
        description="Actions and lifecycle controls for this application."
      />

      <div className="rounded-2xl border border-border bg-zinc-950/70 p-5">
        <h2 className="mb-4 text-sm font-medium text-zinc-400">Application actions</h2>
        <ProjectActions applicationId={id} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run typecheck**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web typecheck 2>&1 | tail -20
```

Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/\(console\)/projects/\[id\]/env/page.tsx apps/web/src/app/\(console\)/projects/\[id\]/domains/page.tsx apps/web/src/app/\(console\)/projects/\[id\]/settings/page.tsx
git commit -m "feat(console): add Env, Domains, Settings sub-pages (reuse EnvManager / ProjectActions)"
```

---

## Task 7: Create Metrics and Errors Stub Pages

**Files:**
- Create: `apps/web/src/app/(console)/projects/[id]/metrics/page.tsx`
- Create: `apps/web/src/app/(console)/projects/[id]/errors/page.tsx`

**Interfaces:**
- Consumes: `Card`, `CardHeader` from `@/components/ui/card`, `FontAwesomeIcon` from `@fortawesome/react-fontawesome`, `faChartLine`, `faBug` from `@/lib/icons`, `PageHeader` from `@/components/ui/page-header`.
- Produces: two routable stub pages with intentional "coming soon" empty-state cards.

These stubs must look like production pages, not broken placeholders. They should use the `Card` + a large icon + heading + subtitle layout (same premium feel as the rest of the console).

- [ ] **Step 1: Create `metrics/page.tsx`**

```typescript
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { faChartLine } from "@/lib/icons"

export default function MetricsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Observability"
        title="Metrics"
        description="Real-time resource utilization and performance data."
      />
      <Card className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <FontAwesomeIcon
          icon={faChartLine}
          className="h-10 w-10 text-zinc-600"
        />
        <div>
          <h2 className="text-lg font-semibold text-zinc-200">Live metrics coming soon</h2>
          <p className="mt-2 max-w-sm text-sm text-zinc-500">
            CPU, memory, and request-rate charts from the Coolify observability stack will
            appear here once the metrics backend is wired up.
          </p>
        </div>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Create `errors/page.tsx`**

```typescript
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { faBug } from "@/lib/icons"

export default function ErrorsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Reliability"
        title="Errors"
        description="Application error events and exception tracking."
      />
      <Card className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <FontAwesomeIcon
          icon={faBug}
          className="h-10 w-10 text-zinc-600"
        />
        <div>
          <h2 className="text-lg font-semibold text-zinc-200">Error tracking coming soon</h2>
          <p className="mt-2 max-w-sm text-sm text-zinc-500">
            Exception counts, stack traces, and error frequency will surface here once an
            error-tracking integration is configured for this project.
          </p>
        </div>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: Run typecheck**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm --dir apps/web typecheck 2>&1 | tail -20
```

Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/\(console\)/projects/\[id\]/metrics/page.tsx apps/web/src/app/\(console\)/projects/\[id\]/errors/page.tsx
git commit -m "feat(console): add Metrics and Errors stub pages (coming-soon empty-state cards)"
```

---

## Task 8: Full Green `pnpm web:check` + Final Integration Commit

**Files:**
- No new files (verification step + report writing).

**Interfaces:**
- Consumes: all files from Tasks 1–7.
- Produces: green `pnpm web:check`, written report at `.superpowers/sdd/task-r3b-report.md`.

- [ ] **Step 1: Run the full check suite**

```bash
cd /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host && pnpm web:check 2>&1
```

Expected output includes:
- `eslint .` — 0 errors, 0 warnings
- `tsc --noEmit` — exits 0
- `vitest run` — all tests pass (including the 4 new `ProjectSubNav` tests)

If the lint step reports an `@typescript-eslint` or `next/no-*` violation in the new files, fix it in-place before the report.

If typecheck reports a "stale `.next` types" error (e.g., referencing an old path that no longer exists), note it in the report — the implementer can run `rm -rf apps/web/.next` to clear the incremental build cache and re-run typecheck.

- [ ] **Step 2: Write the report**

```bash
mkdir -p /Users/magnetoid/Documents/trae_projects/tetra-host/tetra-host/.superpowers/sdd
```

Then write the report to `.superpowers/sdd/task-r3b-report.md` with:
1. Status: DONE or BLOCKED.
2. Commit SHA + subject for the final commit.
3. Exact `pnpm web:check` result (pass/fail + test count).
4. Sub-nav sections: which are live (Overview, Deployments, Logs, Env, Domains, Settings) vs. stubbed (Metrics, Errors).
5. Next.js docs consulted (the nested-layout API and dynamic-segment `params` API).
6. Any concerns or follow-up items.

**Do NOT `git add` the report file.**

- [ ] **Step 3: Create the final integration commit**

Collect all staged changes from throughout the tasks (there should be none left unstaged since each task committed):

```bash
git log --oneline -10
```

If all individual task commits are present, create one final summary commit that ties it together — or just verify the history is clean. If the user's original task specified a single commit, squash using an interactive rebase:

```bash
# Find the base commit before Task 1 started
git log --oneline | grep -A1 "per-project"
# Squash all task commits into one:
# git rebase -i <base-sha>
# (replace all "pick" lines after the first with "squash")
```

**Alternatively**, keep the per-task commits as-is (better for review). The spec says one commit message so if squashing: use this message:

```
feat(console): per-project layout with left sub-nav (deployments/logs/env/domains + metrics/errors stubs)
```

---

## Self-Review Checklist

**Spec coverage check:**

| Spec requirement | Task that implements it |
|---|---|
| `layout.tsx` with left sub-nav | Task 3 |
| `ProjectSubNav` client component with `usePathname` | Task 2 |
| Overview page (status + domain + latest dep) | Task 4 |
| Deployments page (reuse `DeployConsole`) | Task 5 |
| Logs page (reuse `DeployConsole`/`LogStream`) | Task 5 |
| Env page (reuse `EnvManager`) | Task 6 |
| Domains page (project domain + DNS link) | Task 6 |
| Metrics stub (coming-soon card) | Task 7 |
| Errors stub (coming-soon card) | Task 7 |
| Settings page (reuse `ProjectActions`) | Task 6 |
| Active-state highlighting in sub-nav | Task 2 |
| Each section reachable by URL | Tasks 5–7 |
| FA icons (no lucide) | Task 1 |
| shadcn/ui + Font Awesome + dark premium look | All tasks |
| Vitest smoke test for sub-nav | Task 2 |
| `pnpm web:check` green | Task 8 |
| Report file at `.superpowers/sdd/task-r3b-report.md` | Task 8 |
| Stale `.next` types noted if encountered | Task 8 |

**Placeholder scan:** No TBDs or "implement later" patterns. All code blocks are complete.

**Type consistency:**
- `ProjectSubNav` props: `{ id: string; projectName: string }` — used this way in Task 3's layout.
- `DeployConsole` props: `{ applicationId: string; initialDeployments: ProjectDeploymentRecord[] }` — imported as-is, not changed.
- `EnvManager` props: `{ applicationId: string; initialEnvs: EnvVar[] }` — imported as-is, not changed.
- `ProjectActions` props: `{ applicationId: string }` — imported as-is, not changed.
- All `params` are typed as `Promise<{ id: string }>` and awaited — consistent with Next 15/16 API.
- `projects.find((p) => p.id === id)` returns `ProjectRecord | undefined`; `notFound()` narrows the type — used consistently across Tasks 4–6.
