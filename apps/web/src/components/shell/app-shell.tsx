import Link from "next/link"

import { ConsoleNav } from "@/components/shell/console-nav"
import { PendingGate } from "@/components/shell/pending-gate"
import { UserMenu } from "@/components/ui/user-menu"
import { APP_ENV, APP_NAME } from "@/lib/env"
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
      <aside className="hidden w-72 border-r border-border bg-muted/40 p-6 lg:block">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-sm font-bold">
            CI
          </div>
          <div>
            <div className="font-semibold">{APP_NAME}</div>
            <div className="text-xs text-zinc-400">Hosting Panel</div>
          </div>
        </Link>

        <div className="mt-6 rounded-2xl border border-border bg-background/60 p-4 text-sm">
          <div className="text-zinc-400">Environment</div>
          <div className="mt-2 font-medium capitalize">{APP_ENV}</div>
          {admin.tenant_name ? (
            <div className="mt-3 text-xs text-zinc-500">
              Tenant: {admin.tenant_name}
            </div>
          ) : null}
        </div>

        <ConsoleNav adminRole={admin.role} projects={projects} />
      </aside>

      <main className="flex-1">
        <header className="flex h-16 items-center justify-between border-b border-border px-6">
          <div>
            <div className="text-sm text-zinc-400">
              Python core · Coolify · Mailcow · Cloudflare
            </div>
            <div className="text-xs text-zinc-500">Cloud Industry control plane</div>
          </div>
          <UserMenu admin={admin} />
        </header>
        <section className="p-6 lg:p-10">{children}</section>
      </main>
    </div>
  )
}
