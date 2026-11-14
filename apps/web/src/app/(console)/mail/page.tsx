import { redirect } from "next/navigation"

/** Mail moved into Domains (ADR 0019): each domain has a Mail tab. */
export default function MailPage() {
  redirect("/domains")
}
