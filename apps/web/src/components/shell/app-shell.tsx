import Link from "next/link"
import { ViewTransition } from "react"

import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { CommandMenu } from "@/components/command/command-menu"
import { PendingGate } from "@/components/shell/pending-gate"
import { StatusSpine } from "@/components/shell/status-spine"
import { TopTabs } from "@/components/shell/top-tabs"
import { UserMenu } from "@/components/ui/user-menu"
import type { AdminRecord } from "@/lib/types"

export function AppShell({
  admin,
  children,
}: {
  admin: AdminRecord
  children: React.ReactNode
}) {
  // Pending owners (role === "owner" with a non-active tenant) see the gate.
  if (admin.role === "owner" && admin.tenant_status !== "active") {
    return <PendingGate admin={admin} />
  }

  const isPlatformAdmin = admin.role === "platform_admin"

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to content
      </a>

      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/dashboard" className="flex items-center gap-2">
            <TetraWordmark />
          </Link>
          <span className="text-muted-foreground/40">/</span>
          {admin.tenant_name ? (
            <span className="inline-flex max-w-[12rem] items-center gap-1.5 truncate rounded-md border border-border px-2.5 py-1 text-sm">
              <span className="truncate">{admin.tenant_name}</span>
            </span>
          ) : null}
          {isPlatformAdmin ? (
            <span className="rounded-md border border-primary/40 bg-primary/5 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider text-primary">
              Platform
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          <CommandMenu adminRole={admin.role} />
          <UserMenu admin={admin} />
        </div>
      </header>

      {/* ── Primary tabs ────────────────────────────────────────────────── */}
      <TopTabs adminRole={admin.role} />

      <StatusSpine />

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <main className="flex min-w-0 flex-1 flex-col">
        <section id="main-content" className="mx-auto w-full max-w-[1440px] px-4 py-8 lg:px-8">
          {/* Crossfades page content on every console route change. */}
          <ViewTransition>{children}</ViewTransition>
        </section>
      </main>
    </div>
  )
}
