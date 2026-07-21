/**
 * Theme is a cookie-persisted preference read server-side in the root layout (so the
 * `data-theme` attribute is set before first paint — no flash) and flipped client-side
 * by the account-menu toggle. Default is the light editorial palette; dark is opt-in.
 */
export const THEME_COOKIE = "tetra-theme"

export type Theme = "dark" | "light"

export function normalizeTheme(raw: string | undefined | null): Theme {
  return raw === "dark" ? "dark" : "light"
}

/** Client-only: apply + persist a theme (shared by the account menu and command palette). */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`
}

/** Client-only: read the current theme from the DOM (defaults light for SSR). */
export function getTheme(): Theme {
  if (typeof document === "undefined") return "light"
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light"
}

/** Client-only: flip + persist the theme; returns the new value. */
export function toggleTheme(): Theme {
  const next: Theme = getTheme() === "dark" ? "light" : "dark"
  applyTheme(next)
  return next
}
