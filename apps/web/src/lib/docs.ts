import type { DocEntry } from "@/lib/types"

export const docEntries: DocEntry[] = [
  {
    slug: "getting-started",
    title: "Getting started",
    summary: "Run the Python core locally, bootstrap an admin, and connect the Next.js console.",
    sections: [
      {
        heading: "Prerequisites",
        body: [
          "Python 3.11+, Node.js 20+, and pnpm 9+.",
          "Optional provider credentials for Coolify, Mailcow, and Cloudflare.",
        ],
      },
      {
        heading: "Backend",
        body: [
          "Copy `.env.example` to `.env` and set `APP_SECRET`.",
          "Install dependencies with `uv sync --extra dev`.",
          "Start the API with `uv run uvicorn app.main:app --reload --port 8088`.",
          "Bootstrap an admin with `scripts/bootstrap-admin.sh`.",
        ],
      },
      {
        heading: "Frontend",
        body: [
          "From the repo root run `pnpm install`.",
          "Start the console with `pnpm --filter web dev`.",
          "Sign in at `/auth/login` using your admin credentials.",
        ],
      },
    ],
  },
  {
    slug: "architecture",
    title: "Architecture",
    summary: "How the Next.js console, Python core, and provider integrations fit together.",
    sections: [
      {
        heading: "Control plane split",
        body: [
          "The Python FastAPI core owns auth, tenant isolation, provider orchestration, and operational APIs.",
          "The Next.js app is the browser-facing console and typed BFF for safe session handling.",
        ],
      },
      {
        heading: "Multi-tenant model",
        body: [
          "Admins belong to tenants. Provider resources are mapped to tenants through tenant resource records.",
          "API handlers always scope inventory and actions to the authenticated admin tenant.",
        ],
      },
      {
        heading: "Provider adapters",
        body: [
          "Coolify powers application inventory and deploy/start/restart actions.",
          "Mailcow exposes domain and mailbox visibility.",
          "Cloudflare exposes DNS zone and record visibility.",
        ],
      },
    ],
  },
  {
    slug: "deployment",
    title: "Deployment",
    summary: "Native systemd deployment for the core and Vercel-friendly frontend deployment.",
    sections: [
      {
        heading: "Native backend",
        body: [
          "Use `scripts/install.sh` for the systemd + nginx footprint.",
          "Run `scripts/check-production.sh` before restarting the service.",
          "Set `SESSION_HTTPS_ONLY=true` and `FORCE_HTTPS_REDIRECT=true` behind TLS.",
        ],
      },
      {
        heading: "Frontend on Vercel",
        body: [
          "Deploy `apps/web` as the frontend project.",
          "Set `BACKEND_API_BASE_URL` to your public Python API origin.",
          "Use `/api/health` for deployment checks.",
        ],
      },
    ],
  },
  {
    slug: "contributing",
    title: "Contributing",
    summary: "Quality gates and conventions for extending Tetra Host.",
    sections: [
      {
        heading: "Backend changes",
        body: [
          "Keep route handlers thin and move business logic into services.",
          "Add or update pytest coverage for behavioral changes.",
          "Run `uv run ruff check app tests` before opening a PR.",
        ],
      },
      {
        heading: "Frontend changes",
        body: [
          "Prefer Server Components for read-heavy pages.",
          "Use the typed BFF routes for browser mutations.",
          "Run `pnpm --filter web check` before opening a PR.",
        ],
      },
    ],
  },
]

export function getDocEntry(slug: string): DocEntry | undefined {
  return docEntries.find((entry) => entry.slug === slug)
}
