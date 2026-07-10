import Link from "next/link"

import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { CommandMenu } from "@/components/command/command-menu"
import { ConsoleNav } from "@/components/shell/console-nav"
import { PendingGate } from "@/components/shell/pending-gate"
import { ProjectSwitcher } from "@/components/shell/project-switcher"
import { StatusSpine } from "@/components/shell/status-spine"
import { UserMenu } from "@/components/ui/user-menu"
import { APP_ENV } from "@/lib/env"
import type { AdminRecord } from "@/lib/types"

export function AppShell({
  admin,
  projects = [],
  children,
}: {
  admin: AdminRecord
  projects?: { id: string; name: string }[]
  children: React.ReactNode
}) {
  // Pending owners (role === "owner" with a non-active tenant) see the gate.
  // Platform admins and active owners see the normal console.
  if (admin.role === "owner" && admin.tenant_status !== "active") {
    return <PendingGate admin={admin} />
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-72 shrink-0 border-r border-border bg-muted/40 p-6 lg:block">
        <Link href="/dashboard" className="block">
          <TetraWordmark />
          <div className="mt-2 pl-12 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Control plane
          </div>
        </Link>

        <div className="mt-6 rounded-xl border border-border bg-background/60 p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              Environment
            </span>
            <span className="inline-flex items-center gap-1.5 font-mono text-xs capitalize">
              <span className="size-1.5 rounded-full bg-status-ok" />
              {APP_ENV}
            </span>
          </div>
          {admin.tenant_name ? (
            <div className="mt-2 truncate text-xs text-muted-foreground">
              Tenant: <span className="text-foreground">{admin.tenant_name}</span>
            </div>
          ) : null}
        </div>

        <ConsoleNav adminRole={admin.role} projects={projects} />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border px-6">
          <div className="min-w-0">
            <div className="font-display text-sm font-medium leading-tight">Cloud Industry</div>
            <div className="truncate text-xs text-muted-foreground">Hosting control plane</div>
          </div>
          <div className="flex items-center gap-3">
            {projects.length > 0 ? <ProjectSwitcher projects={projects} /> : null}
            <CommandMenu adminRole={admin.role} />
            <UserMenu admin={admin} />
          </div>
        </header>
        <StatusSpine />
        <section className="p-6 lg:p-10">{children}</section>
      </main>
    </div>
  )
}
