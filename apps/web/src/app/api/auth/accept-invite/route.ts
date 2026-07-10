import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { fetchBackend } from "@/lib/api"
import { SESSION_COOKIE_NAME } from "@/lib/env"
import type { LoginResponse } from "@/lib/types"
import { ADMIN_PROFILE_COOKIE, sessionCookieOptions } from "@/lib/session"

export async function POST(request: Request) {
  const payload = (await request.json()) as {
    token?: string
    full_name?: string
    password?: string
  }

  if (!payload.token || !payload.full_name || !payload.password) {
    return NextResponse.json(
      { error: "Name and password are required." },
      { status: 400 },
    )
  }

  try {
    const result = await fetchBackend<LoginResponse>("/auth/accept-invite", {
      method: "POST",
      body: {
        token: payload.token,
        full_name: payload.full_name,
        password: payload.password,
      },
    })

    if (!result.token) {
      return NextResponse.json({ error: "Invite could not be redeemed." }, { status: 400 })
    }

    const jar = await cookies()
    jar.set(SESSION_COOKIE_NAME, result.token, sessionCookieOptions())
    jar.set(ADMIN_PROFILE_COOKIE, JSON.stringify(result.admin), {
      ...sessionCookieOptions(),
      httpOnly: false,
    })

    return NextResponse.json({ ok: true, admin: result.admin })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invite could not be redeemed."
    return NextResponse.json({ error: message }, { status: 422 })
  }
}
