import Link from "next/link"
import { redirect } from "next/navigation"

import { LoginForm } from "@/components/auth/login-form"
import { TetraMark } from "@/components/brand/tetra-mark"
import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { getConsoleSession } from "@/lib/auth"
import { safeNextPath } from "@/lib/utils"

type LoginPageProps = {
  searchParams: Promise<{ next?: string }>
}

const PLANES = [
  { code: "APPS", provider: "Coolify" },
  { code: "MAIL", provider: "Mailcow" },
  { code: "DNS", provider: "Cloudflare" },
  { code: "EDGE", provider: "Operational" },
]

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
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      {/* Left: the control plane */}
      <section className="relative hidden overflow-hidden border-r border-border bg-muted lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        {/* faint blueprint grid */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            backgroundImage:
              "linear-gradient(rgba(124,58,237,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.05) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
            maskImage:
              "radial-gradient(ellipse 90% 80% at 40% 40%, #000 40%, transparent 100%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 90% 80% at 40% 40%, #000 40%, transparent 100%)",
          }}
        />

        <div className="relative flex items-center justify-between">
          <Link href="/">
            <TetraWordmark />
          </Link>
          <span className="font-[family-name:var(--font-jetbrains-mono)] text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            control&nbsp;plane
          </span>
        </div>

        <div className="relative flex flex-1 items-center justify-center py-10">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute h-72 w-72 rounded-full blur-md"
            style={{
              background:
                "radial-gradient(circle at 50% 45%, rgba(124,58,237,0.35), rgba(34,211,238,0.10) 40%, transparent 68%)",
            }}
          />
          <TetraMark className="relative h-[340px] w-[380px] max-w-full" />
        </div>

        <div className="relative">
          <h1 className="font-[family-name:var(--font-space-grotesk)] text-[2.6rem] font-semibold leading-[1.05] tracking-tight">
            Deploy the whole stack
            <br />
            from{" "}
            <span className="bg-gradient-to-r from-violet-400 via-violet-500 to-cyan-400 bg-clip-text text-transparent">
              one plane.
            </span>
          </h1>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-muted-foreground">
            Applications, databases, DNS, and mail — orchestrated behind a single, tenant-aware
            control plane.
          </p>

          <div className="mt-8 grid max-w-md grid-cols-2 gap-x-8 gap-y-3 font-[family-name:var(--font-jetbrains-mono)] text-[12px]">
            {PLANES.map((plane, i) => (
              <div key={plane.code} className="flex items-center gap-2.5">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-status-ok"
                  style={{ animation: `tetraPulse 2.4s ${i * 0.6}s ease-in-out infinite` }}
                />
                <span className="text-foreground">{plane.code}</span>
                <span className="text-muted-foreground">{plane.provider}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Right: sign in */}
      <section className="relative flex items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-sm">
          <div className="mb-10 lg:hidden">
            <Link href="/">
              <TetraWordmark />
            </Link>
          </div>

          <div className="font-[family-name:var(--font-jetbrains-mono)] text-[11px] uppercase tracking-[0.2em] text-primary">
            Admin access
          </div>
          <h2 className="mt-2 font-[family-name:var(--font-space-grotesk)] text-3xl font-semibold tracking-tight">
            Sign in
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">Access your Tetra AI Cloud control plane.</p>

          <LoginForm nextPath={nextPath} />

          <div className="mt-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="font-[family-name:var(--font-jetbrains-mono)] text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Secured
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <div className="mt-4 flex flex-wrap justify-center gap-x-5 gap-y-2 font-[family-name:var(--font-jetbrains-mono)] text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="h-1 w-1 rounded-full bg-status-ok" />
              CSRF protected
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1 w-1 rounded-full bg-status-ok" />
              Rate limited
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-1 w-1 rounded-full bg-status-ok" />
              Signed sessions
            </span>
          </div>

          <p className="mt-10 text-center text-xs text-muted-foreground">
            New here?{" "}
            <Link href="/auth/register" className="text-foreground hover:underline">
              Create an account
            </Link>
          </p>
        </div>
      </section>
    </div>
  )
}
