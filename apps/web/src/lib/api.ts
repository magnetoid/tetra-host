import { BACKEND_API_BASE_URL } from "@/lib/env"

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

type FetchBackendOptions = {
  token?: string
  method?: string
  body?: unknown
  searchParams?: Record<string, string | undefined>
}

function buildUrl(path: string, searchParams?: Record<string, string | undefined>): URL {
  const normalizedPath = path.replace(/^\//, "")
  const base = BACKEND_API_BASE_URL.endsWith("/")
    ? BACKEND_API_BASE_URL
    : `${BACKEND_API_BASE_URL}/`
  const url = new URL(normalizedPath, base)

  if (searchParams) {
    for (const [key, value] of Object.entries(searchParams)) {
      if (value !== undefined) {
        url.searchParams.set(key, value)
      }
    }
  }

  return url
}

export async function fetchBackend<T>(
  path: string,
  options: FetchBackendOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  }

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`
  }

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json"
  }

  const response = await fetch(buildUrl(path, options.searchParams), {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        detail = payload.detail
      }
    } catch {
      // Keep status text fallback.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function proxyBackendRequest(
  path: string,
  request: Request,
  token?: string,
): Promise<Response> {
  const url = buildUrl(path, Object.fromEntries(new URL(request.url).searchParams.entries()))
  const headers = new Headers()
  headers.set("Accept", "application/json")

  const contentType = request.headers.get("content-type")
  if (contentType) {
    headers.set("Content-Type", contentType)
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const body =
    request.method === "GET" || request.method === "HEAD" ? undefined : await request.text()

  const response = await fetch(url, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
  })

  const responseBody = await response.text()
  return new Response(responseBody, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
    },
  })
}
