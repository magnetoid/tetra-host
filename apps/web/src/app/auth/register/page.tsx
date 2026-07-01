import Link from "next/link"
import { redirect } from "next/navigation"

import { RegisterForm } from "@/components/auth/register-form"
import { TetraMark } from "@/components/brand/tetra-mark"
import { TetraWordmark } from "@/components/brand/tetra-wordmark"
import { getConsoleSession } from "@/lib/auth"

const CAPABILITIES = [
  { code: "DEPLOY", copy: "Push-to-deploy with live build logs and instant rollback." },
  { code: "DNS+MAIL", copy: "Cloudflare DNS and mailboxes managed in one place." },
  { code: "ISOLATED", copy: "Your resources stay scoped to your organisation — always." },
]

export default async function RegisterPage() {
  const session = await getConsoleSession()
  if (session) {
    redirect("/dashboard")
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      {/* Left: the control plane */}
      <section className="relative hidden overflow-hidden border-r border-border bg-muted lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
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
          <span className="font-[family-name:var(--font-jetbrains-mono)] text-[11px] uppercase tracking-[0.2em] text-zinc-600">
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
            Host your stack on{" "}
            <span className="bg-gradient-to-r from-violet-400 via-violet-500 to-cyan-400 bg-clip-text text-transparent">
              one platform.
            </span>
          </h1>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-zinc-400">
            Deploy applications, manage DNS, and run mail — through a unified, tenant-aware control
            plane built for serious teams.
          </p>

          <div className="mt-8 grid max-w-md gap-y-3 font-[family-name:var(--font-jetbrains-mono)] text-[12px]">
            {CAPABILITIES.map((cap) => (
              <div key={cap.code} className="flex items-start gap-3">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                <span>
                  <span className="text-zinc-300">{cap.code}</span>{" "}
                  <span className="text-zinc-600">{cap.copy}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Right: create account */}
      <section className="relative flex items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-sm">
          <div className="mb-10 lg:hidden">
            <Link href="/">
              <TetraWordmark />
            </Link>
          </div>

          <div className="font-[family-name:var(--font-jetbrains-mono)] text-[11px] uppercase tracking-[0.2em] text-violet-300">
            Get started
          </div>
          <h2 className="mt-2 font-[family-name:var(--font-space-grotesk)] text-3xl font-semibold tracking-tight">
            Create an account
          </h2>
          <p className="mt-2 text-sm text-zinc-500">
            Your account is reviewed by an admin before you get access.
          </p>

          <RegisterForm />

          <p className="mt-10 text-center text-xs text-zinc-600">
            Already have an account?{" "}
            <Link href="/auth/login" className="text-zinc-300 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </div>
  )
}
