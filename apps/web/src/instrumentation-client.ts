/**
 * Client-side observability (runs before hydration). Error reporting goes to
 * the platform's GlitchTip sidecar via its Sentry-compatible DSN; everything
 * is a no-op (zero bundle cost — dynamic import) until a DSN is configured.
 */
const dsn = process.env.NEXT_PUBLIC_GLITCHTIP_DSN

if (dsn) {
  import("@sentry/browser")
    .then((Sentry) => {
      Sentry.init({
        dsn,
        environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
        // Console errors are already visible locally; sample conservatively.
        sampleRate: 1,
        tracesSampleRate: 0,
      })
    })
    .catch(() => {
      // Never let observability break the app.
    })
}
