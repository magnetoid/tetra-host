import { AppShell } from "@/components/shell/app-shell"
import { requireConsoleSession } from "@/lib/auth"

export default async function ConsoleLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const session = await requireConsoleSession()

  return <AppShell admin={session.admin}>{children}</AppShell>
}
