/**
 * Next.js Middleware — Production Route Protection (Auth Phase 2)
 *
 * Protected routes redirect to /login when no valid JWT is present.
 * The JWT is stored in the httpOnly "cortex_access" cookie
 * (written by backend auth routes on login/refresh).
 *
 * We perform a lightweight presence + expiry check here (no signature
 * verification — that happens on every API call to the backend).
 */
import { NextRequest, NextResponse } from "next/server"

const IS_DEVELOPMENT = process.env.NODE_ENV !== "production"

// ==========================================
// ROUTE CONFIG
// ==========================================

// Exact paths that are always public
const PUBLIC_EXACT = new Set(["/", "/login"])

// Path prefixes that are always public
const PUBLIC_PREFIXES = ["/_next", "/favicon", "/api/auth", "/static", "/images"]

// Protected paths — must be authenticated
const PROTECTED_PREFIXES = [
    "/command",
    "/cognition",
    "/memory",
    "/voice",
    "/operator",
    "/governance",
    "/settings",
    "/runtime",
    "/analytics",
    "/workspace",
    "/executive",
    "/demo",
    "/governance-center",
    "/memory-explorer",
    "/replay",
]

const NONCE_HEADER = "x-nonce"

function buildContentSecurityPolicy(nonce: string): string {
    const styleSrc = IS_DEVELOPMENT ? "style-src 'self' 'unsafe-inline'" : "style-src 'self'"
    const styleSrcElem = IS_DEVELOPMENT ? "style-src-elem 'self' 'unsafe-inline'" : "style-src-elem 'self'"
    const connectSrc = IS_DEVELOPMENT ? "connect-src 'self' http: https: ws: wss:" : "connect-src 'self' https: wss:"

    const directives = [
        "default-src 'self'",
        `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${IS_DEVELOPMENT ? " 'unsafe-eval'" : ""}`,
        styleSrc,
        styleSrcElem,
        "style-src-attr 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        connectSrc,
        "media-src 'self' blob:",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]

    if (!IS_DEVELOPMENT) {
        directives.push("upgrade-insecure-requests")
    }

    return directives.join("; ")
}

function buildNonce(): string {
    return btoa(crypto.randomUUID())
}

function attachSecurityHeaders(
    request: NextRequest,
    response: NextResponse,
    nonce?: string,
): NextResponse {
    if (nonce) {
        const requestHeaders = new Headers(request.headers)
        const contentSecurityPolicy = buildContentSecurityPolicy(nonce)

        requestHeaders.set(NONCE_HEADER, nonce)
        requestHeaders.set("Content-Security-Policy", contentSecurityPolicy)

        const securedResponse = NextResponse.next({
            request: { headers: requestHeaders },
        })

        securedResponse.headers.set(NONCE_HEADER, nonce)
        securedResponse.headers.set("Content-Security-Policy", contentSecurityPolicy)
        return securedResponse
    }

    return response
}

// ==========================================
// HELPERS
// ==========================================

function getTokenFromCookie(request: NextRequest): string | null {
    return request.cookies.get("cortex_access")?.value ?? null
}

function isTokenExpired(token: string): boolean {
    try {
        const [, payload] = token.split(".")
        const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")))
        if (!decoded.exp) return false
        // Add 10s grace period for clock skew
        return Date.now() >= (decoded.exp * 1000) - 10_000
    } catch {
        // Can't parse — treat as expired
        return true
    }
}

// ==========================================
// MIDDLEWARE
// ==========================================

export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl
    const nonce = buildNonce()

    // 1. Always allow public exact paths
    if (PUBLIC_EXACT.has(pathname)) return attachSecurityHeaders(request, NextResponse.next(), nonce)

    // 2. Always allow public prefixes (Next.js internals, auth API, static)
    if (PUBLIC_PREFIXES.some((p) => pathname.startsWith(p))) return NextResponse.next()

    // 3. Only guard explicitly protected paths — everything else passes through
    const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))
    if (!isProtected) return attachSecurityHeaders(request, NextResponse.next(), nonce)

    // 4. Extract token from cookie
    const token = getTokenFromCookie(request)

    if (!token || isTokenExpired(token)) {
        const loginUrl = new URL("/login", request.url)
        loginUrl.searchParams.set("next", pathname)
        // Clear stale cookie on redirect
        const response = NextResponse.redirect(loginUrl)
        response.headers.set("Content-Security-Policy", buildContentSecurityPolicy(nonce))
        response.headers.set(NONCE_HEADER, nonce)
        if (!token) return response
        // Token exists but expired — clear it
        response.cookies.delete("cortex_access")
        response.cookies.delete("cortex_refresh")
        return response
    }

    // Token present and not expired — allow through
    return attachSecurityHeaders(request, NextResponse.next(), nonce)
}

export const config = {
    matcher: [
        "/((?!_next/static|_next/image|favicon.ico).*)",
    ],
}

