import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"
import { notFound } from "next/navigation"

import { ProjectSubNav } from "@/components/projects/project-sub-nav"
import { AppStatus } from "@/components/ui/app-status"
import { fetchBackend } from "@/lib/api"
import { requireConsoleSession } from "@/lib/auth"
import { faEnvelope } from "@/lib/icons"
import type { MailResponse, ProjectRecord } from "@/lib/types"

type AppLayoutProps = {
  children: React.ReactNode
  params: Promise<{ project: string; app: string }>
}

export default async function AppLayout({ children, params }: AppLayoutProps) {
  const session = await requireConsoleSession()
  const { project, app } = await params

  const [projects, mail] = await Promise.all([
    fetchBackend<ProjectRecord[]>("/projects", { token: session.token }).catch(
      () => [] as ProjectRecord[],
    ),
    fetchBackend<MailResponse>("/mail", { token: session.token }).catch(
      () => ({ providers: [], domains: [], mailboxes: [] }) as MailResponse,
    ),
  ])

  const record = projects.find((p) => p.id === app)
  if (!record) {
    notFound()
  }

  const projectName = record.project_name || record.name
  const mailDomain = mail.domains.find((d) => d.domain_name === record.primary_domain)

  return (
    <div className="space-y-6">
      {/* Persistent entity header — every app tab is anchored by name · status ·
          live domain · breadcrumb, so you always know what you're operating on. */}
      <header className="space-y-2 border-b border-border pb-5">
        <nav className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
          <Link href="/projects" className="transition-colors hover:text-foreground">
            Projects
          </Link>
          <span aria-hidden>/</span>
          <Link
            href={`/projects/${project}`}
            className="truncate transition-colors hover:text-foreground"
          >
            {projectName}
          </Link>
          <span aria-hidden>/</span>
          <span className="truncate text-foreground">{record.name}</span>
        </nav>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{record.name}</h1>
          <AppStatus value={record.status} />
          {mailDomain ? (
            <Link
              href={`/projects/${project}/apps/${app}/domains`}
              className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
              title={`${mailDomain.mailboxes} mailboxes on ${mailDomain.domain_name}`}
            >
              <FontAwesomeIcon icon={faEnvelope} className="h-3 w-3" />
              <span className="tabular-nums">{mailDomain.mailboxes}</span>
            </Link>
          ) : null}
          {record.primary_domain ? (
            <a
              href={`https://${record.primary_domain}`}
              target="_blank"
              rel="noreferrer"
              className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
            >
              <span className="font-mono text-xs">{record.primary_domain}</span>
              <span aria-hidden>↗</span>
            </a>
          ) : null}
        </div>
      </header>

      {/* Desktop: the main sidebar slides to this app's menu (see ConsoleNav).
          Mobile (no sidebar): a horizontal app bar carries the same menu. */}
      <div className="lg:hidden">
        <ProjectSubNav
          projectSlug={project}
          appId={app}
          projectName={projectName}
          appName={record.name}
        />
      </div>
      <main className="min-w-0">{children}</main>
    </div>
  )
}
