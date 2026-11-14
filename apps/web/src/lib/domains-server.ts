import { cache } from "react"

import { fetchBackend } from "@/lib/api"
import type { DomainsOverview } from "@/lib/types"

/** One overview fetch per request, shared by the domain layout and its tab page. */
export const loadDomainsOverview = cache(
  (token: string): Promise<DomainsOverview> =>
    fetchBackend<DomainsOverview>("/domains/overview", { token }),
)
