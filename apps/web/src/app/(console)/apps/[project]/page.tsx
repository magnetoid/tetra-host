import { redirect } from "next/navigation"

/** An app opens on its deployments. */
export default async function AppPage({ params }: { params: Promise<{ project: string }> }) {
  const { project } = await params
  redirect(`/apps/${project}/deployments`)
}
