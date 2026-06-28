import { cookies } from "next/headers"

import { SESSION_COOKIE_NAME } from "@/lib/env"
import type { AdminRecord } from "@/lib/types"

export const ADMIN_PROFILE_COOKIE = "tetra_host_admin_profile"

export async function getSessionToken(): Promise<string | undefined> {
  const jar = await cookies()
  return jar.get(SESSION_COOKIE_NAME)?.value
}

export async function getAdminProfile(): Promise<AdminRecord | undefined> {
  const jar = await cookies()
  const raw = jar.get(ADMIN_PROFILE_COOKIE)?.value
  if (!raw) {
    return undefined
  }

  try {
    return JSON.parse(raw) as AdminRecord
  } catch {
    return undefined
  }
}

export function sessionCookieOptions(maxAgeSeconds = 60 * 60 * 24 * 7) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: maxAgeSeconds,
  }
}
