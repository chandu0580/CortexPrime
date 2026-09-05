/**
 * The ONLY channel between this browser and CortexPrime.
 *
 * Everything the investigator workspace shows comes through here, and here
 * reaches exactly one place: the governed Product API. There is no provider
 * call, no connector, no worker, no credential broker and no V1 route in this
 * file, and adding one would be visible in a five-line diff.
 *
 * Identity
 * --------
 * No function in this module takes a tenant. It cannot: the access token is an
 * HttpOnly cookie the browser attaches and this code can never read, and the
 * backend resolves the tenant from that verified token. A tenant put in a query
 * string, a header or a body by this client would be ignored by the server
 * (proven in Phase 10.1, checks B6-B8) -- so it is not sent at all, rather than
 * sent and ignored.
 */

/**
 * Same-origin by default.
 *
 * `/product-api` is rewritten to the Product API process by `next.config.ts`.
 * Going through the app's own origin means the CSP's `connect-src 'self'` is
 * satisfied without widening it, and the HttpOnly session cookie is carried the
 * way it is for any same-origin request — no credentialed cross-origin call and
 * no CORS allowance for the browser at all.
 */
const DEFAULT_PRODUCT_API = "/product-api"

function stripTrailingSlash(value: string): string {
    return value.endsWith("/") ? value.slice(0, -1) : value
}

export function productApiBase(): string {
    const configured = stripTrailingSlash(
        process.env.NEXT_PUBLIC_PRODUCT_API_URL ?? "",
    )
    return configured || DEFAULT_PRODUCT_API
}

/**
 * How a request failed, kept distinct from how the *world* is.
 *
 * A 401 is not "unknown", a 503 is not "conflicted", and neither is evidence
 * about anything. Part M of this phase turns on that separation: transport
 * failures live in this class, epistemic states live in the response body, and
 * the two are never rendered by the same component.
 */
export class ProductApiError extends Error {
    readonly status: number
    readonly kind:
        | "unauthenticated"
        | "no-tenant"
        | "not-found"
        | "invalid-request"
        | "unavailable"
        | "network"
        | "server"

    constructor(status: number, message: string) {
        super(message)
        this.name = "ProductApiError"
        this.status = status
        this.kind =
            status === 401 ? "unauthenticated"
            : status === 403 ? "no-tenant"
            : status === 404 ? "not-found"
            : status === 422 ? "invalid-request"
            : status === 503 ? "unavailable"
            : status === 0 ? "network"
            : "server"
    }
}

/** A GET against the Product API. There is deliberately no post/put/delete. */
export async function productGet<T>(
    path: string,
    params?: Record<string, string | number | boolean | undefined>,
    signal?: AbortSignal,
): Promise<T> {
    // A relative base resolves against the app's own origin. `window.location`
    // is the right base in the browser; on the server there is no origin to
    // resolve against, which is correct -- these reads belong to a signed-in
    // browser session and must not be made without one.
    const base = productApiBase()
    const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin
    const url = new URL(`${base}${path}`, base.startsWith("http") ? undefined : origin)
    for (const [key, value] of Object.entries(params ?? {})) {
        if (value === undefined) continue
        // A guard, not a formality. If a future caller ever tries to pass a
        // tenant from the client, it must fail loudly here rather than be
        // quietly ignored by the server and look supported.
        if (key === "tenant" || key === "tenant_id" || key === "tenant_slug") {
            throw new Error(
                "the client must never send a tenant: identity comes from the " +
                "authenticated session, and the server ignores anything else",
            )
        }
        url.searchParams.set(key, String(value))
    }

    let response: Response
    try {
        response = await fetch(url.toString(), {
            method: "GET",
            // The HttpOnly session cookie. No token is read, held or attached
            // by this code, so there is nothing here for a script to steal.
            credentials: "include",
            headers: { Accept: "application/json" },
            signal,
        })
    } catch (cause) {
        throw new ProductApiError(
            0,
            cause instanceof Error && cause.name === "AbortError"
                ? "request cancelled"
                : "CortexPrime could not be reached",
        )
    }

    if (!response.ok) {
        // The server's messages are written to be safe to show; anything
        // unexpected is replaced rather than rendered.
        let detail = ""
        try {
            const body = (await response.json()) as { detail?: string; message?: string }
            detail = body?.detail || body?.message || ""
        } catch {
            detail = ""
        }
        throw new ProductApiError(response.status, detail || response.statusText)
    }

    return (await response.json()) as T
}
