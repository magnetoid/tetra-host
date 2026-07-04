import type { Metadata } from "next"
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google"
import { config } from "@fortawesome/fontawesome-svg-core"
import "@fortawesome/fontawesome-svg-core/styles.css"
import { cookies } from "next/headers"

import { APP_NAME } from "@/lib/env"
import { THEME_COOKIE, normalizeTheme } from "@/lib/theme"

import "./globals.css"

// We import Font Awesome's CSS above; stop it injecting a second copy (avoids icon flash).
config.autoAddCss = false

// Tetra AI Cloud brand type system (ADR 0003): Space Grotesk display, Inter body,
// JetBrains Mono for data/status. All variable fonts — no explicit weights needed.
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
})

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
})

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
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
      className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  )
}
