"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { CommandMenu } from "@/components/command/command-menu"
import { Breadcrumbs } from "@/components/shell/breadcrumbs"
import { Sidebar, SidebarNav } from "@/components/shell/sidebar"
import { SystemStatus } from "@/components/shell/system-status"
import { ThemeToggle } from "@/components/shell/theme-toggle"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { UserMenu } from "@/components/ui/user-menu"
import { faBars } from "@/lib/icons"
import { SIDEBAR_COOKIE, type Theme } from "@/lib/theme"
import type { AdminRecord } from "@/lib/types"
import { teamRef } from "@/lib/workspace"

/**
 * Console chrome: scope sidebar on the left (drawer on small screens), a thin top
 * bar with breadcrumbs, ⌘K, system status, theme and account. Page content goes
 * in `children`.
 */
export function ConsoleFrame({
  admin,
  theme,
  initialCollapsed,
  children,
}: {
  admin: AdminRecord
  theme: Theme
  initialCollapsed: boolean
  children: React.ReactNode
}) {
  const isPlatformAdmin = admin.role === "platform_admin"
  const team = teamRef(admin)
  const [collapsed, setCollapsed] = useState(initialCollapsed)
  const [drawerOpen, setDrawerOpen] = useState(false)

  function toggleCollapsed() {
    const next = !collapsed
    setCollapsed(next)
    document.cookie = `${SIDEBAR_COOKIE}=${next ? "collapsed" : "expanded"}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`
  }

  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <Sidebar isPlatformAdmin={isPlatformAdmin} team={team} collapsed={collapsed} onToggle={toggleCollapsed} />

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="w-72 gap-0 bg-sidebar p-3 pt-14">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SidebarNav isPlatformAdmin={isPlatformAdmin} team={team} onNavigate={() => setDrawerOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-13 shrink-0 items-center gap-2 border-b border-border bg-background/95 px-3 backdrop-blur lg:px-5">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="inline-flex size-9 items-center justify-center rounded-md text-foreground hover:bg-accent lg:hidden"
          >
            <FontAwesomeIcon icon={faBars} className="size-4" />
          </button>
          <Breadcrumbs isPlatformAdmin={isPlatformAdmin} />
          <div className="flex-1" />
          <div className="flex items-center gap-1.5">
            <CommandMenu adminRole={admin.role} />
            <SystemStatus />
            <ThemeToggle initial={theme} />
            <UserMenu admin={admin} />
          </div>
        </header>

        <main id="main-content" className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-7 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
