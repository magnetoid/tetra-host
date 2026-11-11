"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useState } from "react"

import { faMoon, faSun } from "@/lib/icons"
import { applyTheme, type Theme } from "@/lib/theme"

/** Icon button that flips light/dark. The server passes the cookie value so the icon is right on first paint. */
export function ThemeToggle({ initial }: { initial: Theme }) {
  const [theme, setTheme] = useState<Theme>(initial)
  const next: Theme = theme === "dark" ? "light" : "dark"
  return (
    <button
      type="button"
      onClick={() => {
        applyTheme(next)
        setTheme(next)
      }}
      aria-label={next === "dark" ? "Switch to dark theme" : "Switch to light theme"}
      className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
    >
      <FontAwesomeIcon icon={theme === "dark" ? faSun : faMoon} className="size-3.5" />
    </button>
  )
}
