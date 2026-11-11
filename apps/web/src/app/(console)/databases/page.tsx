import { redirect } from "next/navigation"

// Managed databases were Coolify-backed and are removed until the engine provides them (ADR 0018).
export default function DatabasesRedirect() {
  redirect("/deploys")
}
