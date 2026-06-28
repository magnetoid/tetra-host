import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { fetchBackend } from "@/lib/api"
import { SESSION_COOKIE_NAME } from "@/lib/env"
import type { LoginResponse } from "@/lib/types"
import { ADMIN_PROFILE_COOKIE, sessionCookieOptions } from "@/lib/session"
import { safeNextPath } from "@/lib/utils"

export async function POST(request: Request) {
  const payload = (await request.json()) as {
    email?: string
    password?: string
    next?: string
  }

  if (!payload.email || !payload.password) {
    return NextResponse.json({ error: "Email and password are required." }, { status: 400 })
  }

  try {
    const login = await fetchBackend<LoginResponse>("/auth/login", {
      method: "POST",
      body: {
        email: payload.email,
        password: payload.password,
      },
    })

    const jar = await cookies()
    jar.set(SESSION_COOKIE_NAME, login.token, sessionCookieOptions())
    jar.set(ADMIN_PROFILE_COOKIE, JSON.stringify(login.admin), {
      ...sessionCookieOptions(),
      httpOnly: false,
    })

    return NextResponse.json({
      ok: true,
      next: safeNextPath(payload.next),
      admin: login.admin,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid credentials."
    return NextResponse.json({ error: message }, { status: 401 })
  }
}
