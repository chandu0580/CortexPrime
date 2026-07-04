import type { NextConfig } from "next"

const nextConfig: NextConfig = {
    reactStrictMode: false,

    // Produce a standalone output bundle for the production Docker image.
    // The builder stage copies .next/standalone + .next/static + public/
    // into a minimal Node.js image (no node_modules required at runtime).
    output: process.env.NODE_ENV === "production" ? "standalone" : undefined,

}

export default nextConfig