"use client"

/**
 * Data access for the investigator workspace.
 *
 * Every hook here reads the Product API and nothing else. None takes a tenant:
 * the server resolves it from the session, so a tenant is not part of any query
 * key either — a cache keyed by a client-supplied tenant would be a cache a
 * client could aim at another tenant.
 */

import { useQuery } from "@tanstack/react-query"

import { productGet } from "@/lib/product-api"
import type {
    AssuranceList,
    InvestigationDetail,
    InvestigationList,
    Timeline,
    WorldState,
} from "@/lib/investigator/types"

export const investigatorKeys = {
    all: ["investigator"] as const,
    list: (state: string) => ["investigator", "list", state] as const,
    detail: (ref: string) => ["investigator", "detail", ref] as const,
    timeline: (ref: string) => ["investigator", "timeline", ref] as const,
    assurance: (ref: string) => ["investigator", "assurance", ref] as const,
    world: (subject: string, predicate: string) =>
        ["investigator", "world", subject, predicate] as const,
}

/**
 * Authentication and authorisation outcomes are not retried.
 *
 * Retrying a 401 or 403 cannot change the answer, and retrying a 404 would make
 * a deliberate cross-tenant refusal look like a flaky endpoint.
 */
function retryPolicy(failureCount: number, error: unknown): boolean {
    const status = (error as { status?: number } | null)?.status ?? 0
    if ([401, 403, 404, 422].includes(status)) return false
    return failureCount < 2
}

export function useInvestigations(state: "all" | "active" | "completed" = "all") {
    return useQuery({
        queryKey: investigatorKeys.list(state),
        queryFn: ({ signal }) =>
            productGet<InvestigationList>("/api/v1/investigations", { state, limit: 50 }, signal),
        retry: retryPolicy,
    })
}

export function useInvestigation(ref: string) {
    return useQuery({
        queryKey: investigatorKeys.detail(ref),
        queryFn: ({ signal }) =>
            productGet<InvestigationDetail>(`/api/v1/investigations/${encodeURIComponent(ref)}`, undefined, signal),
        enabled: Boolean(ref),
        retry: retryPolicy,
    })
}

export function useTimeline(ref: string) {
    return useQuery({
        queryKey: investigatorKeys.timeline(ref),
        queryFn: ({ signal }) =>
            productGet<Timeline>(`/api/v1/investigations/${encodeURIComponent(ref)}/timeline`, undefined, signal),
        enabled: Boolean(ref),
        retry: retryPolicy,
    })
}

export function useAssurance(ref: string) {
    return useQuery({
        queryKey: investigatorKeys.assurance(ref),
        queryFn: ({ signal }) =>
            productGet<AssuranceList>(`/api/v1/investigations/${encodeURIComponent(ref)}/assurance`, undefined, signal),
        enabled: Boolean(ref),
        retry: retryPolicy,
    })
}

/**
 * Current World state.
 *
 * `staleTime: 0` on purpose. Freshness is computed by the server against the
 * server's clock and returned with a `read_at`; serving that from a 30-second
 * browser cache would show a freshness verdict that is itself out of date,
 * which is precisely the "stale evidence rendered as current" risk Phase 10.0
 * assigned to this phase. The response's own `read_at` is displayed alongside.
 */
export function useWorldState(subjectRef: string, predicate: string) {
    return useQuery({
        queryKey: investigatorKeys.world(subjectRef, predicate),
        queryFn: ({ signal }) =>
            productGet<WorldState>(
                "/api/v1/world/state",
                { subject_ref: subjectRef, predicate },
                signal,
            ),
        enabled: Boolean(subjectRef && predicate),
        staleTime: 0,
        gcTime: 0,
        retry: retryPolicy,
    })
}
