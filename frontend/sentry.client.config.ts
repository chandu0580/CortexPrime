// Sentry client-side initialization
// See https://docs.sentry.io/platforms/javascript/guides/nextjs/
import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: process.env.NODE_ENV,
    release: `cortexprime-frontend@${process.env.NEXT_PUBLIC_BUILD_HASH ?? "dev"}`,

    // Capture 10% of transactions for performance monitoring
    tracesSampleRate: 0.1,

    // Replay 1% of sessions, 10% of error sessions
    replaysSessionSampleRate: 0.01,
    replaysOnErrorSampleRate: 0.10,

    integrations: [
      Sentry.replayIntegration({
        maskAllText:    true,
        blockAllMedia:  true,
      }),
      Sentry.browserTracingIntegration(),
    ],

    // Sanitize sensitive data from breadcrumbs
    beforeBreadcrumb(breadcrumb) {
      if (breadcrumb.category === "xhr" || breadcrumb.category === "fetch") {
        // Don't log auth token values in breadcrumbs
        if (breadcrumb.data?.url?.includes("/auth/")) {
          breadcrumb.data = { ...breadcrumb.data, body: "[REDACTED]" };
        }
      }
      return breadcrumb;
    },
  });
}
