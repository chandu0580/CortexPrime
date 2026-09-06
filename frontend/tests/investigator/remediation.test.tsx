import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import EpistemicBadge from "@/components/investigator/EpistemicBadge"
import { productPost } from "@/lib/product-api"
import { readApproval, readStage } from "@/lib/investigator/remediation-vocabulary"

afterEach(() => {
    vi.unstubAllGlobals()
})

/**
 * Phase 10.3's frontend guarantees, asserted directly.
 *
 * The browser is untrusted. These tests are about what it is structurally
 * incapable of sending, and about the fact that no stage in the remediation
 * lifecycle is rendered as a generic success.
 */

describe("the browser cannot assert anything that governs the action", () => {
    const forbidden = {
        tenant_id: "another-tenant",
        capability_ref: "platform.anything",
        namespace: "kube-system",
        name: "coredns",
        action_digest: "0".repeat(64),
        approval_digest: "0".repeat(64),
        risk: "low",
        side_effect_class: "read",
        code_trust: "fixed",
        isolation_tier: "sealed",
        blast_radius: "none",
        autonomy_level: "a4_autonomous",
        actor: "admin",
        actor_ref: "human:someone-else",
        execution_ref: "exec-forged",
    }

    for (const [key, value] of Object.entries(forbidden)) {
        it(`refuses to send "${key}"`, async () => {
            const fetchMock = vi.fn()
            vi.stubGlobal("fetch", fetchMock)
            await expect(
                productPost("/api/v1/approvals/appr-1/decision", {
                    decision: "approve", [key]: value,
                }),
            ).rejects.toThrow(/not something this client may send/)
            // Not merely rejected server-side: never sent at all.
            expect(fetchMock).not.toHaveBeenCalled()
        })
    }

    it("refuses to POST to any path outside the three governed routes", async () => {
        const fetchMock = vi.fn()
        vi.stubGlobal("fetch", fetchMock)
        for (const path of [
            "/api/v1/investigations",
            "/api/v1/executions",
            "/api/v1/autonomy",
            "/api/v1/approvals",
            "/api/v1/workers/execute",
            "/api/v1/approvals/appr-1/execute/../../autonomy",
        ]) {
            await expect(productPost(path, {})).rejects.toThrow(/may not POST/)
        }
        expect(fetchMock).not.toHaveBeenCalled()
    })

    it("does send the three fields a human legitimately provides", async () => {
        const fetchMock = vi.fn(async () =>
            new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }))
        vi.stubGlobal("fetch", fetchMock)

        await productPost("/api/v1/approvals/appr-1/decision", {
            decision: "approve", justification: "checked the preview",
            confirm_workload: "payments-api",
        })
        const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
        expect(init.credentials).toBe("include")
        expect(JSON.parse(String(init.body))).toEqual({
            decision: "approve",
            justification: "checked the preview",
            confirm_workload: "payments-api",
        })
    })
})

describe("no stage is rendered as a generic success", () => {
    it("APPROVED is not EXECUTING and neither claims the world changed", () => {
        expect(readStage("granted").label).toBe("APPROVED")
        expect(readStage("granted").meaning).toMatch(/not executed/i)
        expect(readStage("executing").meaning).toMatch(/NOT yet established/i)
    })

    it("OUTCOME ESTABLISHED credits an independent observation, not the worker", () => {
        expect(readStage("outcome_established").meaning).toMatch(/INDEPENDENT/)
        expect(readStage("outcome_established").meaning).toMatch(/not the worker's own report/i)
    })

    it("VERIFIED is a separate stage from OUTCOME ESTABLISHED", () => {
        expect(readStage("verified").label).not.toBe(readStage("outcome_established").label)
    })

    it("REFUSED is a decision, not a malfunction", () => {
        const reading = readStage("refused")
        expect(reading.meaning).toMatch(/a decision, not a malfunction/i)
        expect(reading.tone).not.toBe("disputed")
    })

    it("FAILED does not claim nothing happened", () => {
        expect(readStage("failed").meaning).toMatch(/UNKNOWN until it is observed/)
        expect(readStage("failed").meaning).toMatch(/does not mean nothing happened/i)
    })

    it("EXPIRED is distinguished from REJECTED", () => {
        expect(readStage("expired").label).toBe("EXPIRED")
        expect(readStage("expired").meaning).toMatch(/Nobody changed their mind/i)
        expect(readStage("rejected").label).toBe("REJECTED")
    })

    it("an expired grant reads as EXPIRED, not as APPROVED", () => {
        expect(readApproval("granted", true).label).toBe("EXPIRED")
        expect(readApproval("granted", false).label).toBe("APPROVED")
    })

    it("no stage emits a percentage, a confidence or the word success", () => {
        for (const stage of ["proposed", "pending", "granted", "denied", "withdrawn",
                             "expired", "executing", "outcome_established", "verified",
                             "insufficient_evidence", "refused", "failed", null]) {
            const { label, meaning } = readStage(stage)
            const text = `${label} ${meaning}`.toLowerCase()
            expect(text).not.toMatch(/\d+\s*%/)
            expect(text).not.toMatch(/\bconfidence\b/)
            expect(text).not.toMatch(/\bguaranteed\b/)
            expect(text).not.toMatch(/\bsuccess\b/)
        }
    })

    it("renders the stage name as text, so it is never colour alone", () => {
        render(<EpistemicBadge reading={readStage("refused")} />)
        expect(screen.getByText("REFUSED")).toBeInTheDocument()
    })
})
