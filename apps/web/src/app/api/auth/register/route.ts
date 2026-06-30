import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { fetchBackend } from "@/lib/api"
import { SESSION_COOKIE_NAME } from "@/lib/env"
import type { LoginResponse } from "@/lib/types"
import { ADMIN_PROFILE_COOKIE, sessionCookieOptions } from "@/lib/session"

export async function POST(request: Request) {
  const payload = (await request.json()) as {
    org_name?: string
    email?: string
    password?: string
  }

  if (!payload.org_name || !payload.email || !payload.password) {
    return NextResponse.json(
      { error: "Organisation name, email, and password are required." },
      { status: 400 },
    )
  }

  try {
    const result = await fetchBackend<LoginResponse>("/auth/signup", {
      method: "POST",
      body: {
        org_name: payload.org_name,
        email: payload.email,
        password: payload.password,
      },
    })

    // Duplicate email returns an empty non-authenticating token — treat as success
    // (non-distinguishing by design) but don't set cookies for an empty token.
    if (!result.token) {
      return NextResponse.json({ ok: true })
    }

    const jar = await cookies()
    jar.set(SESSION_COOKIE_NAME, result.token, sessionCookieOptions())
    jar.set(ADMIN_PROFILE_COOKIE, JSON.stringify(result.admin), {
      ...sessionCookieOptions(),
      httpOnly: false,
    })

    return NextResponse.json({ ok: true, admin: result.admin })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Registration failed."
    return NextResponse.json({ error: message }, { status: 422 })
  }
}
