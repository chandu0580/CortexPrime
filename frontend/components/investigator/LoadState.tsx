"use client"

import { ProductApiError } from "@/lib/product-api"

/**
 * Transport and authorisation outcomes — kept strictly apart from epistemic ones.
 *
 * Part M: a stale World observation is not a failed HTTP request, and an
 * investigation that concluded INSUFFICIENT_EVIDENCE is not a system error.
 * Those live in the response body and are rendered by `EpistemicBadge`. What
 * this component renders is the other kind of thing entirely — the request did
 * not produce a body at all — and it never borrows the epistemic vocabulary to
 * say so.
 */

const MESSAGES: Record<string, { title: string; detail: string }> = {
    unauthenticated: {
        title: "Not signed in",
        detail: "This session is not authenticated. Sign in to continue.",
    },
    "no-tenant": {
        title: "No tenant on this session",
        detail:
            "The signed-in account is not associated with an active tenant, so " +
            "there is nothing it is permitted to read. This is enforced by the " +
            "backend; it cannot be set from this screen.",
    },
    "not-found": {
        title: "Not found",
        detail:
            "No such record exists for this tenant. Records belonging to other " +
            "tenants are reported the same way, on purpose.",
    },
    "invalid-request": {
        title: "The request was rejected",
        detail: "The parameters were outside what this endpoint accepts.",
    },
    unavailable: {
        title: "The engine is not available",
        detail:
            "The governed engine is not composed in this process. This says " +
            "nothing about the state of your infrastructure.",
    },
    network: {
        title: "CortexPrime could not be reached",
        detail:
            "The request did not complete. Nothing is known about the world " +
            "from this attempt — this is not evidence that anything is wrong.",
    },
    server: {
        title: "The request failed",
        detail: "The server could not complete this read.",
    },
}

export function Loading({ label }: { label: string }) {
    return (
        <div role="status" aria-live="polite" className="flex items-center gap-2 py-6">
            <span
                className="h-2 w-2 animate-pulse rounded-full"
                style={{ background: "var(--accent-primary)" }}
                aria-hidden="true"
            />
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Loading {label}…
            </span>
        </div>
    )
}

export function RequestFailure({ error, label }: { error: unknown; label: string }) {
    const kind = error instanceof ProductApiError ? error.kind : "server"
    const message = MESSAGES[kind] ?? MESSAGES.server
    return (
        <div
            role="alert"
            className="rounded-lg border px-4 py-3"
            style={{ borderColor: "var(--border-strong)", background: "var(--surface-raised)" }}
        >
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                {message.title}
            </p>
            <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {message.detail}
            </p>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                Could not load {label}. This is a request outcome, not a finding about your systems.
            </p>
        </div>
    )
}

/** Nothing to show, said plainly — never dressed up as a clean result. */
export function Empty({ children }: { children: React.ReactNode }) {
    return (
        <p className="py-4 text-sm" style={{ color: "var(--text-muted)" }}>
            {children}
        </p>
    )
}
