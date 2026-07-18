const DEFAULT_BACKEND_API_BASE_URL = "http://127.0.0.1:8088/api/v1"

export const APP_NAME = "Tetra Host"
export const SESSION_COOKIE_NAME = "tetra_host_console_session"
export const APP_ENV = process.env.NEXT_PUBLIC_APP_ENV ?? "development"
export const BACKEND_API_BASE_URL =
  process.env.BACKEND_API_BASE_URL ?? DEFAULT_BACKEND_API_BASE_URL
export const APP_BASE_URL = process.env.NEXT_PUBLIC_APP_URL ?? "http://127.0.0.1:3000"
// Public origin of the FastAPI panel (e.g. https://panel.cloud-industry.com).
// Used for browser-redirect flows that must run on the panel's origin/session —
// today the OIDC "Open webmail" launch. Empty = the feature stays hidden.
export const PANEL_PUBLIC_URL = process.env.PANEL_PUBLIC_URL ?? ""
