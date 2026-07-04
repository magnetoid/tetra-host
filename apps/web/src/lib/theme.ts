/**
 * Theme is a cookie-persisted preference read server-side in the root layout (so the
 * `data-theme` attribute is set before first paint — no flash) and flipped client-side
 * by the account-menu toggle. Default is dark.
 */
export const THEME_COOKIE = "tetra-theme"

export type Theme = "dark" | "light"

export function normalizeTheme(raw: string | undefined | null): Theme {
  return raw === "light" ? "light" : "dark"
}
