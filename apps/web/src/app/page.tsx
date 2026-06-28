import Link from "next/link"

import { APP_NAME } from "@/lib/env"
import { publicNavItems } from "@/lib/navigation"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-sm font-bold">
              CI
            </div>
            <div>
              <div className="font-semibold">{APP_NAME}</div>
              <div className="text-xs text-zinc-500">Cloud Industry hosting control plane</div>
            </div>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            {publicNavItems.map((item) => (
              <Link key={item.href} href={item.href} className="text-zinc-400 hover:text-white">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-16 lg:py-24">
        <section className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-zinc-500">Open source control plane</p>
            <h1 className="mt-4 max-w-3xl text-5xl font-semibold tracking-tight lg:text-6xl">
              A premium hosting panel for Coolify, Mailcow, and Cloudflare.
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-zinc-400">
              Tetra Host combines a hardened Python core with a modern Next.js console so operators
              can monitor provider health, review deployment state, and manage tenant-scoped
              infrastructure from one place.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/auth/login"
                className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
              >
                Open console
              </Link>
              <Link
                href="/docs"
                className="rounded-xl border border-border px-5 py-3 text-sm font-semibold text-zinc-200 transition hover:bg-zinc-900"
              >
                Read the docs
              </Link>
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-muted p-8">
            <div className="text-sm text-zinc-500">Built for operators</div>
            <div className="mt-6 space-y-4">
              {[
                "Multi-tenant admin sessions with typed API contracts",
                "Coolify application inventory and deploy controls",
                "Mailcow domain and mailbox visibility",
                "Cloudflare DNS zone and record browsing",
              ].map((item) => (
                <div key={item} className="rounded-2xl border border-border bg-background/70 p-4 text-sm text-zinc-300">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
