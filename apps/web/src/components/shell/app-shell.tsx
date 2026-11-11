import { cookies } from "next/headers"
import { ViewTransition } from "react"

import { ConsoleFrame } from "@/components/shell/console-frame"
import { PendingGate } from "@/components/shell/pending-gate"
import { ScopeLabelsProvider } from "@/components/shell/scope-labels"
import { normalizeTheme, SIDEBAR_COOKIE, THEME_COOKIE } from "@/lib/theme"
import type { AdminRecord } from "@/lib/types"

export async function AppShell({
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

  const jar = await cookies()
  const theme = normalizeTheme(jar.get(THEME_COOKIE)?.value)
  const collapsed = jar.get(SIDEBAR_COOKIE)?.value === "collapsed"

  return (
    <ScopeLabelsProvider team={admin.tenant_name}>
      <ConsoleFrame admin={admin} theme={theme} initialCollapsed={collapsed}>
        {/* Crossfades page content on every console route change. */}
        <ViewTransition>{children}</ViewTransition>
      </ConsoleFrame>
    </ScopeLabelsProvider>
  )
}
