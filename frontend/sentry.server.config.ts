// Sentry server-side (Node.js / Edge) initialization
import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment:      process.env.NODE_ENV,
    release:          `cortexprime-frontend@${process.env.NEXT_PUBLIC_BUILD_HASH ?? "dev"}`,
    tracesSampleRate: 0.1,
  });
}
