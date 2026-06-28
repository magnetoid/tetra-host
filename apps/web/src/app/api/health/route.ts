import { NextResponse } from "next/server"

import { APP_ENV, APP_NAME } from "@/lib/env"

export async function GET() {
  return NextResponse.json({
    ok: true,
    app: APP_NAME,
    env: APP_ENV,
    version: "web-console",
    requestId: crypto.randomUUID(),
  })
}
