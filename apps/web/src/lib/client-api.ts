"use client"

/**
 * Client-side API access for `/api/proxy/*` — the one place JSON parsing and
 * error-message extraction happen. Replaces the hand-rolled
 * `fetch → res.json().catch → payload.detail ?? "…"` blocks that were
 * copy-pasted across ~40 client components.
 */

export class ClientApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ClientApiError"
    this.status = status
  }
}

type ApiRequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"
  body?: unknown
  /** Fallback message when the backend didn't send a usable `detail`. */
  errorMessage?: string
}

/**
 * Fetch a `/api/proxy/*` path, throwing `ClientApiError` with the backend's
 * `detail` (or a fallback) on non-2xx. Returns parsed JSON, or undefined for 204.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers:
      options.body !== undefined
        ? { "Content-Type": "application/json", Accept: "application/json" }
        : { Accept: "application/json" },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new ClientApiError(
      response.status,
      payload.detail ?? options.errorMessage ?? "Request failed — please retry.",
    )
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json().catch(() => undefined)) as T
}
