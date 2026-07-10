import { NextResponse } from "next/server"

import { fetchBackend } from "@/lib/api"

type SsoAuthorize = { authorize_url: string }

/** Public origin as the browser sees it (behind the nginx proxy). */
function publicOrigin(request: Request): string {
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? "localhost"
  const proto = request.headers.get("x-forwarded-proto") ?? "https"
  return `${proto}://${host}`
}

export async function GET(
  request: Request,
  context: { params: Promise<{ slug: string }> },
) {
  const { slug } = await context.params
  const origin = publicOrigin(request)
  const redirectUri = `${origin}/auth/sso/callback`

  try {
    const { authorize_url } = await fetchBackend<SsoAuthorize>(
      `/auth/sso/${encodeURIComponent(slug)}/authorize`,
      { searchParams: { redirect_uri: redirectUri } },
    )
    return NextResponse.redirect(authorize_url)
  } catch {
    return NextResponse.redirect(
      `${origin}/auth/login?sso_error=${encodeURIComponent("Single sign-on is unavailable for this workspace.")}`,
    )
  }
}
