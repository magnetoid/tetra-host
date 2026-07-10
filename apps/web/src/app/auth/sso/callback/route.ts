import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { fetchBackend } from "@/lib/api"
import { SESSION_COOKIE_NAME } from "@/lib/env"
import type { LoginResponse } from "@/lib/types"
import { ADMIN_PROFILE_COOKIE, sessionCookieOptions } from "@/lib/session"

function publicOrigin(request: Request): string {
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? "localhost"
  const proto = request.headers.get("x-forwarded-proto") ?? "https"
  return `${proto}://${host}`
}

export async function GET(request: Request) {
  const origin = publicOrigin(request)
  const url = new URL(request.url)
  const code = url.searchParams.get("code")
  const state = url.searchParams.get("state")
  const idpError = url.searchParams.get("error")
  const loginError = (msg: string) =>
    NextResponse.redirect(`${origin}/auth/login?sso_error=${encodeURIComponent(msg)}`)

  if (idpError) return loginError("The identity provider cancelled the sign-in.")
  if (!code || !state) return loginError("The sign-in response was incomplete.")

  try {
    const result = await fetchBackend<LoginResponse>("/auth/sso/callback", {
      method: "POST",
      body: {
        code,
        state,
        // Must match the redirect_uri used to start the flow.
        redirect_uri: `${origin}/auth/sso/callback`,
      },
    })
    if (!result.token) return loginError("Single sign-on did not return a session.")

    const jar = await cookies()
    jar.set(SESSION_COOKIE_NAME, result.token, sessionCookieOptions())
    jar.set(ADMIN_PROFILE_COOKIE, JSON.stringify(result.admin), {
      ...sessionCookieOptions(),
      httpOnly: false,
    })
    return NextResponse.redirect(`${origin}/dashboard`)
  } catch (error) {
    const message = error instanceof Error ? error.message : "Single sign-on failed."
    return loginError(message)
  }
}
