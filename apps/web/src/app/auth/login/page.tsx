import Link from "next/link"
import { redirect } from "next/navigation"

import { LoginForm } from "@/components/auth/login-form"
import { getConsoleSession } from "@/lib/auth"
import { safeNextPath } from "@/lib/utils"

type LoginPageProps = {
  searchParams: Promise<{ next?: string }>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  // Validate the session (not just cookie presence) — otherwise a stale/expired cookie
  // bounces login -> dashboard -> login forever ("too many redirects").
  const session = await getConsoleSession()
  const params = await searchParams
  const nextPath = safeNextPath(params.next)

  if (session) {
    redirect(nextPath)
  }

  return (
    <div className="min-h-screen bg-background px-6 py-10 lg:px-10">
      <div className="mx-auto max-w-6xl">
        <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Back to home
        </Link>
        <div className="mt-8 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-3xl border border-border bg-muted p-8 lg:p-10">
            <div className="text-sm text-zinc-500">Cloud Industry Operations</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight">
              Secure access to your hosting control plane.
            </h1>
            <p className="mt-4 max-w-2xl text-zinc-400">
              Monitor provider health, review deployment state, and manage platform operations
              through a hardened admin session.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-3">
              {[
                {
                  title: "Operational visibility",
                  copy: "Coolify, Mailcow, and Cloudflare data flows into one admin view.",
                },
                {
                  title: "Safer sessions",
                  copy: "Signed tokens, protected routes, and typed backend contracts.",
                },
                {
                  title: "Tenant-aware core",
                  copy: "Inventory and actions stay scoped to the authenticated tenant.",
                },
              ].map((item) => (
                <div key={item.title} className="rounded-2xl border border-border bg-background/70 p-4">
                  <div className="font-medium">{item.title}</div>
                  <div className="mt-2 text-sm text-zinc-500">{item.copy}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="mx-auto w-full max-w-md rounded-3xl border border-border bg-muted p-8">
            <h2 className="text-2xl font-bold">Sign in</h2>
            <p className="mt-2 text-sm text-zinc-400">Use your platform admin account to continue.</p>
            <LoginForm nextPath={nextPath} />
            <div className="mt-4 text-xs text-zinc-500">
              Administrative actions are tied to your account and tenant context.
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
