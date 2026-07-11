import { redirect } from "next/navigation"

type AppDetailPageProps = {
  params: Promise<{ project: string; app: string }>
}

/**
 * An app's home IS its deployments. Landing on
 * `/projects/<project>/apps/<app>` sends you straight to the Deployments view.
 */
export default async function AppDetailPage({ params }: AppDetailPageProps) {
  const { project, app } = await params
  redirect(`/projects/${project}/apps/${app}/deployments`)
}
