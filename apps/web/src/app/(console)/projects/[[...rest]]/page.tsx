import { redirect } from "next/navigation"

// The Coolify-backed project pages are gone (ADR 0018). Old links land on the
// engine deploys list until the hierarchy screens give projects their own addresses.
export default function ProjectsRedirect() {
  redirect("/deploys")
}
