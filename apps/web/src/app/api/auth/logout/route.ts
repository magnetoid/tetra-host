import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { SESSION_COOKIE_NAME } from "@/lib/env"
import { ADMIN_PROFILE_COOKIE } from "@/lib/session"

export async function POST(request: Request) {
  const jar = await cookies()
  jar.delete(SESSION_COOKIE_NAME)
  jar.delete(ADMIN_PROFILE_COOKIE)

  const url = new URL("/auth/login", request.url)
  return NextResponse.redirect(url)
}
