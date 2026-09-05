import type { NextConfig } from "next"

// The governed Product API runs as its own process (ADR-094): it is
// deliberately not mounted beside the tenant-unaware V1 routes.
const PRODUCT_API_ORIGIN =
    process.env.PRODUCT_API_ORIGIN || "http://localhost:8110"

const nextConfig: NextConfig = {
    reactStrictMode: true,

    output: process.env.NODE_ENV === "production" ? "standalone" : undefined,

    // The workspace reaches the Product API through this SAME-ORIGIN path
    // rather than by calling another origin directly. Two reasons, and neither
    // is convenience:
    //
    //  * The CSP below allows `connect-src 'self' https:`. A direct call to
    //    http://localhost:8100 is blocked by it — and the right response to
    //    that is to stop making a cross-origin call, not to widen the policy.
    //  * Same-origin means no credentialed cross-origin request and no CORS
    //    allowance is needed for the browser at all. The HttpOnly session
    //    cookie is simply carried, as it is for every other same-origin request.
    async rewrites() {
        return [
            {
                source: "/product-api/:path*",
                destination: `${PRODUCT_API_ORIGIN}/:path*`,
            },
        ]
    },

    async headers() {
        return [
            {
                source: "/(.*)",
                headers: [
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    { key: "X-XSS-Protection", value: "1; mode=block" },
                    {
                        key: "Content-Security-Policy",
                        value: [
                            "default-src 'self'",
                            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
                            "style-src 'self' 'unsafe-inline'",
                            "img-src 'self' data: blob: https:",
                            "font-src 'self' data:",
                            "connect-src 'self' https: wss:",
                            "frame-ancestors 'none'",
                            "base-uri 'self'",
                            "form-action 'self'",
                        ].join("; "),
                    },
                ],
            },
        ]
    },
}

export default nextConfig