import Link from "next/link"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"

import { TetraMark } from "@/components/brand/tetra-mark"
import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { faChartLine, faEnvelope, faGlobe, faRocket, faServer, faUsers } from "@/lib/icons"

const GRID_STYLE = {
  backgroundImage:
    "linear-gradient(rgba(124,58,237,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.05) 1px, transparent 1px)",
  backgroundSize: "40px 40px",
  maskImage: "radial-gradient(ellipse 90% 80% at 60% 35%, #000 40%, transparent 100%)",
  WebkitMaskImage: "radial-gradient(ellipse 90% 80% at 60% 35%, #000 40%, transparent 100%)",
} as const

const GLOW_STYLE = {
  background:
    "radial-gradient(circle at 50% 45%, rgba(124,58,237,0.35), rgba(34,211,238,0.10) 40%, transparent 68%)",
} as const

const CAPABILITIES = [
  {
    icon: faRocket,
    title: "Deploy console",
    body: "Ship any git repo — live build logs, instant rollback, preview environments, push-to-deploy.",
    span: "sm:col-span-2",
  },
  { icon: faServer, title: "Coolify apps", body: "Full application inventory with deployment-safe controls." },
  { icon: faGlobe, title: "Cloudflare DNS", body: "Browse and edit zones, records, and traffic analytics." },
  { icon: faEnvelope, title: "Mailcow mail", body: "Domains, mailboxes, aliases, and DKIM at a glance." },
  { icon: faChartLine, title: "Observability", body: "Traffic + error insight via Umami and GlitchTip sidecars." },
  { icon: faUsers, title: "Multi-tenant", body: "Tenant-scoped isolation across data, API, and admin." },
]

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-background/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <TetraWordmark />
          <nav className="flex items-center gap-3 text-sm sm:gap-5">
            <Link href="/docs" className="hidden text-muted-foreground transition-colors hover:text-foreground sm:inline">
              Docs
            </Link>
            <Link href="/auth/login" className="text-muted-foreground transition-colors hover:text-foreground">
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div aria-hidden className="pointer-events-none absolute inset-0 opacity-60" style={GRID_STYLE} />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-28">
          <div>
            <p className="animate-fade-up font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
              Open-source control plane
            </p>
            <h1
              className="animate-fade-up mt-4 font-display text-5xl font-semibold leading-[1.04] tracking-tight lg:text-6xl"
              style={{ animationDelay: "0.05s" }}
            >
              Deploy the whole stack from{" "}
              <span className="bg-gradient-to-r from-violet-400 via-violet-500 to-cyan-400 bg-clip-text text-transparent">
                one plane.
              </span>
            </h1>
            <p
              className="animate-fade-up mt-6 max-w-xl text-lg text-muted-foreground"
              style={{ animationDelay: "0.1s" }}
            >
              Tetra AI Cloud orchestrates Coolify apps, Cloudflare DNS, and Mailcow mail behind a
              single, tenant-aware console — with a deploy engine, live logs, and observability built in.
            </p>
            <div
              className="animate-fade-up mt-8 flex flex-wrap gap-3"
              style={{ animationDelay: "0.15s" }}
            >
              <Link
                href="/auth/register"
                className="inline-flex items-center rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
              >
                <FontAwesomeIcon icon={faRocket} className="mr-2 h-4 w-4" />
                Get started
              </Link>
              <Link
                href="/auth/login"
                className="rounded-xl border border-border px-5 py-3 text-sm font-semibold transition-colors hover:bg-accent"
              >
                Open console
              </Link>
              <Link
                href="/docs"
                className="rounded-xl px-5 py-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
              >
                Docs →
              </Link>
            </div>
          </div>

          <div className="relative flex items-center justify-center">
            <div aria-hidden className="pointer-events-none absolute h-72 w-72 rounded-full blur-md" style={GLOW_STYLE} />
            <TetraMark className="relative h-[300px] w-[340px] max-w-full" />
          </div>
        </div>
      </section>

      {/* Bento capabilities */}
      <section className="mx-auto max-w-6xl px-6 py-16 lg:py-24">
        <div className="max-w-2xl">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            What it orchestrates
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight lg:text-4xl">
            One console for every plane.
          </h2>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((capability, index) => (
            <div
              key={capability.title}
              style={{ animationDelay: `${index * 0.06}s` }}
              className={`animate-fade-up rounded-lg border border-border bg-muted p-6 transition-colors hover:border-primary/30 ${capability.span ?? ""}`}
            >
              <span className="grid size-10 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
                <FontAwesomeIcon icon={capability.icon} className="h-4 w-4" />
              </span>
              <h3 className="mt-4 font-display text-lg font-semibold">{capability.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{capability.body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row">
          <TetraWordmark />
          <div className="flex items-center gap-3 font-mono text-xs text-muted-foreground">
            <span>Tetra AI Cloud</span>
            <span className="text-border">·</span>
            <span>by Cloud Industry</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
