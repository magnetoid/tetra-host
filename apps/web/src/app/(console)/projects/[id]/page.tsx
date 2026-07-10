import { redirect } from "next/navigation"

type ProjectDetailPageProps = {
  params: Promise<{ id: string }>
}

/**
 * A project's home IS its deployments (the two were unified). Landing on
 * `/projects/<id>` sends you straight to the Deployments view.
 */
export default async function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  const { id } = await params
  redirect(`/projects/${id}/deployments`)
}
