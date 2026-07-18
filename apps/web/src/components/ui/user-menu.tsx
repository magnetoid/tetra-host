"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { useState } from "react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { faChevronDown, faCrown, faMoon, faSun, faUser } from "@/lib/icons"
import { applyTheme, type Theme } from "@/lib/theme"
import type { AdminRecord } from "@/lib/types"

/**
 * Upper-right account menu, on the shadcn DropdownMenu + Avatar primitives.
 * Shows the profile, an Account link, a platform-admin-only Super Admin link, a
 * theme toggle, and logout.
 */
export function UserMenu({ admin }: { admin: AdminRecord }) {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document !== "undefined" && document.documentElement.dataset.theme === "light"
      ? "light"
      : "dark",
  )

  const isPlatformAdmin = admin.role === "platform_admin"
  const initial = (admin.full_name || admin.email || "?").charAt(0).toUpperCase()

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark"
    setTheme(next)
    applyTheme(next)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-md border border-border px-1.5 py-1 text-sm outline-none transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/40">
        <Avatar className="size-7">
          <AvatarFallback>{initial}</AvatarFallback>
        </Avatar>
        <span className="hidden text-left sm:block">
          <span className="block text-sm font-medium leading-tight">{admin.full_name}</span>
          <span className="block text-xs leading-tight text-muted-foreground">
            {admin.tenant_name || admin.email}
          </span>
        </span>
        <FontAwesomeIcon icon={faChevronDown} className="h-3 w-3 text-muted-foreground" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="font-normal">
          <div className="text-sm font-medium text-foreground">{admin.full_name}</div>
          <div className="text-xs text-muted-foreground">{admin.email}</div>
          {admin.tenant_name ? (
            <div className="mt-0.5 text-xs text-muted-foreground">{admin.tenant_name}</div>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        <DropdownMenuItem asChild>
          <Link href="/account">
            <FontAwesomeIcon icon={faUser} className="text-muted-foreground" fixedWidth />
            Account
          </Link>
        </DropdownMenuItem>

        {isPlatformAdmin ? (
          <DropdownMenuItem asChild>
            <Link href="/super-admin">
              <FontAwesomeIcon icon={faCrown} className="text-primary" fixedWidth />
              Super Admin
              <Badge variant="outline" className="ml-auto border-primary/30 text-[10px] text-primary">
                PLATFORM
              </Badge>
            </Link>
          </DropdownMenuItem>
        ) : null}

        <DropdownMenuItem onSelect={(e) => e.preventDefault()} onClick={toggleTheme}>
          <FontAwesomeIcon
            icon={theme === "dark" ? faSun : faMoon}
            className="text-muted-foreground"
            fixedWidth
          />
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </DropdownMenuItem>

        <DropdownMenuSeparator />
        <DropdownMenuItem asChild variant="destructive">
          <form action="/api/auth/logout" method="post" className="w-full">
            <button type="submit" className="w-full text-left">
              Log out
            </button>
          </form>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
