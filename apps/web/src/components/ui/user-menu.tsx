"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"

import { faChevronDown, faCrown, faMoon, faSun, faUser } from "@/lib/icons"
import { THEME_COOKIE, type Theme } from "@/lib/theme"
import type { AdminRecord } from "@/lib/types"
import { cn } from "@/lib/utils"

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`
}

/**
 * The upper-right account menu. Headless (no Radix dep): a button trigger + a
 * popover closed on outside-click / Escape. Shows the profile, an Account link, a
 * platform-admin-only Super Admin link, a theme toggle, and logout.
 */
export function UserMenu({ admin }: { admin: AdminRecord }) {
  const [open, setOpen] = useState(false)
  // Lazy-read the SSR-resolved theme. Safe against hydration mismatch: the menu (and
  // thus the theme label) isn't rendered until opened, well after hydration.
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document !== "undefined" && document.documentElement.dataset.theme === "light"
      ? "light"
      : "dark",
  )
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false)
        triggerRef.current?.focus() // return focus to the trigger (menu-button a11y)
      }
    }
    document.addEventListener("mousedown", onClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const isPlatformAdmin = admin.role === "platform_admin"
  const initial = (admin.full_name || admin.email || "?").charAt(0).toUpperCase()

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark"
    setTheme(next)
    applyTheme(next)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm transition hover:bg-zinc-800"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-primary text-xs font-bold text-white">
          {initial}
        </span>
        <span className="hidden text-left sm:block">
          <span className="block text-sm font-medium leading-tight">{admin.full_name}</span>
          <span className="block text-xs leading-tight text-zinc-500">
            {admin.tenant_name || admin.email}
          </span>
        </span>
        <FontAwesomeIcon icon={faChevronDown} className="h-3 w-3 text-zinc-500" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
        >
          <div className="border-b border-border px-4 py-3">
            <div className="text-sm font-medium">{admin.full_name}</div>
            <div className="text-xs text-zinc-500">{admin.email}</div>
            {admin.tenant_name ? (
              <div className="mt-1 text-xs text-zinc-500">{admin.tenant_name}</div>
            ) : null}
          </div>
          <div className="p-1.5">
            <Link
              href="/account"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition hover:bg-zinc-800"
            >
              <FontAwesomeIcon icon={faUser} className="h-4 w-4 text-zinc-500" fixedWidth />
              Account
            </Link>
            {isPlatformAdmin ? (
              <Link
                href="/super-admin"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition hover:bg-zinc-800"
              >
                <FontAwesomeIcon icon={faCrown} className="h-4 w-4 text-primary" fixedWidth />
                Super Admin
                <span className="ml-auto rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                  PLATFORM
                </span>
              </Link>
            ) : null}
            <button
              type="button"
              role="menuitem"
              onClick={toggleTheme}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition hover:bg-zinc-800"
            >
              <FontAwesomeIcon
                icon={theme === "dark" ? faSun : faMoon}
                className="h-4 w-4 text-zinc-500"
                fixedWidth
              />
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
          </div>
          <div className="border-t border-border p-1.5">
            <form action="/api/auth/logout" method="post">
              <button
                type="submit"
                role="menuitem"
                className={cn(
                  "w-full rounded-md px-3 py-2 text-left text-sm text-red-400 transition hover:bg-zinc-800",
                )}
              >
                Log out
              </button>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  )
}
