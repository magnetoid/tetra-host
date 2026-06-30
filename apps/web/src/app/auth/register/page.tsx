import Link from "next/link"
import { redirect } from "next/navigation"

import { RegisterForm } from "@/components/auth/register-form"
import { getConsoleSession } from "@/lib/auth"

export default async function RegisterPage() {
  const session = await getConsoleSession()
  if (session) {
    redirect("/dashboard")
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
              Host your apps on a modern, Vercel-like platform.
            </h1>
            <p className="mt-4 max-w-2xl text-zinc-400">
              Deploy applications, manage DNS, and run mail services through a unified
              control panel built for serious teams.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-3">
              {[
                {
                  title: "Fast deployments",
                  copy: "Push-to-deploy via Coolify with live build logs and rollback.",
                },
                {
                  title: "DNS + Mail",
                  copy: "Cloudflare DNS and Mailcow mail management in one place.",
                },
                {
                  title: "Tenant isolation",
                  copy: "Your resources stay scoped to your organisation — always.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-2xl border border-border bg-background/70 p-4"
                >
                  <div className="font-medium">{item.title}</div>
                  <div className="mt-2 text-sm text-zinc-500">{item.copy}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="mx-auto w-full max-w-md rounded-3xl border border-border bg-muted p-8">
            <h2 className="text-2xl font-bold">Create an account</h2>
            <p className="mt-2 text-sm text-zinc-400">
              Your account is reviewed by an admin before you get access.
            </p>
            <RegisterForm />
            <div className="mt-4 text-xs text-zinc-500">
              Already have an account?{" "}
              <Link href="/auth/login" className="text-zinc-300 hover:underline">
                Sign in
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
