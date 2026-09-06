import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import ApprovalQueue from "@/components/investigator/ApprovalQueue"
import type { ApprovalQueueItem } from "@/lib/investigator/types"

/**
 * The approval inbox's safety rules, asserted directly.
 *
 * The queue is a projection: everything governed on this screen comes from the
 * server, and there is no bulk action. These tests are about both.
 */

function wrap(ui: React.ReactElement) {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

const BASE: ApprovalQueueItem = {
    approval_id: "appr-1",
    investigation_ref: "winv-1",
    incident_ref: "kubernetes:deployment:demo/payments-api",
    requested_by: "human:responder@example.com",
    decided_by: null,
    requested_at: "2026-09-06T09:00:00+00:00",
    decided_at: null,
    expires_at: "2026-09-06T09:30:00+00:00",
    capability_ref: "platform.kubernetes.workload.rollout_restart",
    capability_version: 1,
    capability_digest: "cafe".repeat(16),
    operation: "kubernetes.workload.rollout_restart",
    provider: "kubernetes-contained",
    environment: "development",
    namespace: "demo",
    workload: "payments-api",
    parameters: { namespace: "demo", name: "payments-api" },
    approval_digest: "beef".repeat(16),
    action_digest: null,
    action_digest_note:
        "The ADR-038 action digest covers the binding, which resolution creates " +
        "inside the execution this approval authorizes. It does not exist yet.",
    side_effect_class: "irreversible_write",
    effect_semantics: "non_idempotent_write",
    code_trust: "fixed",
    isolation_tier: "contained",
    reversible: false,
    risk: "high",
    blast_radius: "one Deployment (payments-api) in one namespace (demo)",
    autonomy_ceiling: "a3_approved_action",
    autonomy_requested: "a1_investigate",
    autonomy_allowed: null,
    autonomy_note: "Platform-set ceiling. No autonomy decision is computed here.",
    assurance_status: "not_verified",
    assurance_note: "Assurance has NOT verified this investigation.",
    verification_refs: [],
    evidence_count: 2,
    evidence_refs: ["wobs-1", "wobs-2"],
    state: "pending",
    actionable: true,
    expired: false,
    consumed_by_execution: null,
    justification: "crashloop remediation",
}

function respond(items: ApprovalQueueItem[]) {
    return vi.fn(async () =>
        new Response(JSON.stringify({
            items, count: items.length,
            actionable_count: items.filter((i) => i.actionable).length,
            limit: 50,
            ordering: "actionable first, then risk (critical→low), then oldest first",
            filters: {}, note: "Every approval this tenant may see.",
        }), { status: 200, headers: { "Content-Type": "application/json" } }))
}

afterEach(() => {
    vi.unstubAllGlobals()
})

describe("the inbox shows what a responder needs to triage", () => {
    it("renders a pending approval with its target, risk and state as text", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        expect(await screen.findByText("payments-api")).toBeInTheDocument()
        // Risk and state are words, not colours.
        expect(screen.getByText("high")).toBeInTheDocument()
        expect(screen.getByText("AWAITING APPROVAL")).toBeInTheDocument()
    })

    it("links to the originating investigation without requiring the user to know it", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        const link = await screen.findByRole("link", { name: /winv-1/ })
        expect(link).toHaveAttribute("href", "/investigator/winv-1")
    })

    it("offers Review, never Run or Execute, from a list row", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        const { container } = wrap(<ApprovalQueue />)
        await screen.findByText("payments-api")
        expect(screen.getByRole("button", { name: "Review" })).toBeInTheDocument()
        const text = container.textContent ?? ""
        expect(text).not.toMatch(/\bRun\b/)
        expect(text).not.toMatch(/\bExecute\b/)
        expect(text).not.toMatch(/approve all/i)
    })

    it("has no select-all, no checkbox and no bulk control", async () => {
        vi.stubGlobal("fetch", respond([BASE, { ...BASE, approval_id: "appr-2" }]))
        const { container } = wrap(<ApprovalQueue />)
        await screen.findAllByRole("button", { name: "Review" })
        expect(container.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
        // A bulk ACTION, specifically. The "All" status filter is a filter and
        // matching it would make this assertion about the word rather than the
        // capability.
        expect(screen.queryByRole("button", {
            name: /(approve|reject|run|execute|dismiss)\s*all/i,
        })).toBeNull()
        expect(screen.queryByRole("button", { name: /select\s*all/i })).toBeNull()
    })

    it("says an empty queue is not a statement that nothing needs attention", async () => {
        vi.stubGlobal("fetch", respond([]))
        wrap(<ApprovalQueue />)
        expect(await screen.findByText(/not a statement that/i)).toBeInTheDocument()
    })

    it("shows the server's ordering rather than sorting client-side", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        expect(await screen.findByText(/Ordered by the server/)).toBeInTheDocument()
    })
})

describe("a non-actionable approval offers no decision", () => {
    for (const [label, state] of [
        ["expired", "expired"], ["revoked", "revoked"],
        ["rejected", "rejected"], ["consumed", "consumed"],
    ] as const) {
        it(`an ${label} approval is shown but not decidable`, async () => {
            vi.stubGlobal("fetch", respond([
                { ...BASE, state, actionable: false, expired: state === "expired" },
            ]))
            wrap(<ApprovalQueue />)
            await screen.findByText("payments-api")
            // Present in the record, and with no path to a decision from the row.
            expect(screen.getByRole("button", { name: "Review" })).toBeInTheDocument()
        })
    }
})

describe("the detail screen shows the authoritative action and cannot edit it", () => {
    it("renders the governed facts the server supplied", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()

        await waitFor(() =>
            expect(screen.getByText(/What will happen:/)).toBeInTheDocument())
        expect(screen.getByText("IRREVERSIBLE — there is no inverse action")).toBeInTheDocument()
        expect(screen.getByText("CONTAINED")).toBeInTheDocument()
        expect(screen.getByText("FIXED")).toBeInTheDocument()
        expect(screen.getByText(BASE.approval_digest)).toBeInTheDocument()
    })

    it("reports the action digest as not yet in existence, never invented", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()
        await waitFor(() =>
            expect(screen.getByText("not yet in existence")).toBeInTheDocument())
        expect(screen.getByText(/does not exist yet/i)).toBeInTheDocument()
    })

    it("keeps approve disabled until the workload name is typed", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()
        const approve = await screen.findByRole("button", { name: /Approve this action/ })
        expect(approve).toBeDisabled()
    })

    it("has no input that could change the action itself", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        const { container } = wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()
        await screen.findByRole("button", { name: /Approve this action/ })

        // Exactly two inputs: a reason and a confirmation. Neither is a
        // namespace, a workload, a digest or an autonomy level.
        const inputs = Array.from(container.querySelectorAll("input"))
        expect(inputs).toHaveLength(2)
        expect(inputs.map((i) => i.id).sort()).toEqual(["queue-confirm", "queue-why"])
    })

    it("says a different remediation means rejecting, not editing", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()
        expect(await screen.findByText(/the approved action is never edited/i))
            .toBeInTheDocument()
    })

    it("shows no decision form at all for a non-actionable approval", async () => {
        vi.stubGlobal("fetch", respond([
            { ...BASE, state: "expired", actionable: false, expired: true },
        ]))
        wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()
        await waitFor(() =>
            expect(screen.getByText(/can no longer be decided/i)).toBeInTheDocument())
        expect(screen.queryByRole("button", { name: /Approve this action/ })).toBeNull()
        expect(screen.queryByRole("button", { name: "Reject" })).toBeNull()
    })
})

describe("accessibility, structurally", () => {
    it("labels the filters and the table", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        await screen.findByText("payments-api")
        expect(screen.getByRole("group", { name: /Filter approvals/ })).toBeInTheDocument()
        expect(screen.getByLabelText(/Filter by risk/)).toBeInTheDocument()
        expect(screen.getByRole("table")).toBeInTheDocument()
        for (const heading of ["State", "Remediation", "Investigation", "Requested"]) {
            expect(screen.getByRole("columnheader", { name: heading })).toBeInTheDocument()
        }
    })

    it("marks the active filter with aria-pressed", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        const active = await screen.findByRole("button", { name: "Needs attention" })
        expect(active).toHaveAttribute("aria-pressed", "true")
    })

    it("gives the confirmation input a description", async () => {
        vi.stubGlobal("fetch", respond([BASE]))
        wrap(<ApprovalQueue />)
        ;(await screen.findByRole("button", { name: "Review" })).click()
        const confirm = await screen.findByLabelText(/Type/)
        expect(confirm).toHaveAttribute("aria-describedby", "queue-confirm-help")
    })
})
