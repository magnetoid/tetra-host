import { BACKEND_API_BASE_URL } from "@/lib/env"
import { getSessionToken } from "@/lib/session"

type RouteContext = {
  params: Promise<{ path: string[] }>
}

/**
 * Server-Sent Events proxy.
 *
 * The catch-all `/api/proxy` route buffers the whole response body, which would
 * break streaming. This handler instead pipes the upstream response body straight
 * through without buffering, injecting the Bearer token from the httpOnly session
 * cookie (so the token never reaches the browser) and forwarding client
 * disconnects to the backend so it can stop polling the provider.
 */
export async function GET(request: Request, context: RouteContext) {
  const { path } = await context.params
  const token = await getSessionToken()
  if (!token) {
    return new Response("Unauthorized", { status: 401 })
  }

  const base = BACKEND_API_BASE_URL.endsWith("/")
    ? BACKEND_API_BASE_URL
    : `${BACKEND_API_BASE_URL}/`
  const search = new URL(request.url).search
  const target = new URL(`${path.join("/")}${search}`, base)

  let upstream: Response
  try {
    upstream = await fetch(target, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
      cache: "no-store",
      // Propagate browser disconnect upstream so the backend stops streaming.
      signal: request.signal,
    })
  } catch {
    return new Response("Stream unavailable.", { status: 502 })
  }

  if (!upstream.ok || !upstream.body) {
    return new Response("Stream unavailable.", { status: upstream.status || 502 })
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  })
}
