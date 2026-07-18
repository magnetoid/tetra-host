import Link from "next/link"

import { docEntries } from "@/lib/docs"
import { APP_NAME } from "@/lib/env"

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-background px-6 py-10 lg:px-10">
      <div className="mx-auto max-w-5xl">
        <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Back to home
        </Link>
        <div className="mt-8">
          <p className="text-sm text-zinc-500">{APP_NAME} documentation</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Docs</h1>
          <p className="mt-3 max-w-2xl text-zinc-400">
            Setup guides, architecture notes, and deployment guidance for the open-source control plane.
          </p>
        </div>

        <section className="mt-10 grid gap-4 md:grid-cols-2">
          {docEntries.map((entry) => (
            <Link
              key={entry.slug}
              href={`/docs/${entry.slug}`}
              className="rounded-lg border border-border bg-muted p-6 transition hover:border-zinc-600"
            >
              <h2 className="text-xl font-semibold">{entry.title}</h2>
              <p className="mt-3 text-sm text-zinc-400">{entry.summary}</p>
            </Link>
          ))}
        </section>
      </div>
    </div>
  )
}
