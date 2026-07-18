import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import { config } from "@fortawesome/fontawesome-svg-core"
import "@fortawesome/fontawesome-svg-core/styles.css"
import { cookies } from "next/headers"

import { Toaster } from "@/components/ui/toaster"
import { TooltipProvider } from "@/components/ui/tooltip"
import { APP_NAME } from "@/lib/env"
import { THEME_COOKIE, normalizeTheme } from "@/lib/theme"

import "./globals.css"

// We import Font Awesome's CSS above; stop it injecting a second copy (avoids icon flash).
config.autoAddCss = false

// Professional SaaS type system: Geist for text + display, Geist Mono for
// data/status. Variable fonts — no explicit weights needed.
const geistSans = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: {
    default: APP_NAME,
    template: `%s · ${APP_NAME}`,
  },
  description: "Tetra AI Cloud — a multi-tenant hosting control plane for apps, databases, DNS, and mail.",
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  // Resolve the theme server-side so `data-theme` is set before first paint (no flash).
  const theme = normalizeTheme((await cookies()).get(THEME_COOKIE)?.value)
  return (
    <html
      lang="en"
      data-theme={theme}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <TooltipProvider>{children}</TooltipProvider>
        <Toaster theme={theme} />
      </body>
    </html>
  )
}
