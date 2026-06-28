import Link from "next/link"
import { notFound } from "next/navigation"

import { getDocEntry } from "@/lib/docs"

type DocDetailPageProps = {
  params: Promise<{ slug: string }>
}

export default async function DocDetailPage({ params }: DocDetailPageProps) {
  const { slug } = await params
  const entry = getDocEntry(slug)

  if (!entry) {
    notFound()
  }

  return (
    <div className="min-h-screen bg-background px-6 py-10 lg:px-10">
      <div className="mx-auto max-w-3xl">
        <Link href="/docs" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Back to docs
        </Link>
        <h1 className="mt-8 text-4xl font-semibold tracking-tight">{entry.title}</h1>
        <p className="mt-3 text-zinc-400">{entry.summary}</p>

        <div className="mt-10 space-y-8">
          {entry.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-2xl font-semibold">{section.heading}</h2>
              <ul className="mt-4 space-y-3 text-zinc-300">
                {section.body.map((line) => (
                  <li key={line} className="rounded-xl border border-border bg-muted px-4 py-3 text-sm">
                    {line}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
