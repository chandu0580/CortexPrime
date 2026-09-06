/**
 * The remediation lifecycle vocabulary — Phase 10.3.
 *
 * Its own words, deliberately. Part U of this phase: **no green tick may mean
 * merely HTTP 200.** So there is no "success" state here at all. There is
 * APPROVED, which is not EXECUTING; EXECUTING, which is not OUTCOME
 * ESTABLISHED; and OUTCOME ESTABLISHED, which is not VERIFIED. Each is a
 * different claim about how much is actually known, and collapsing them is how
 * a product ends up telling an operator that something worked because a request
 * returned 200.
 *
 * REFUSED deserves its own note: a governed refusal is a **decision**, not a
 * malfunction, and it is not rendered with the vocabulary used for a failed
 * request.
 */

import type { Reading } from "./epistemic"

function normalise(value: string | null | undefined): string {
    return (value ?? "").trim().toLowerCase().replace(/[\s-]+/g, "_")
}

export function readStage(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "proposed":
            return {
                label: "PROPOSED",
                meaning:
                    "The platform has a governed remediation for this subject. " +
                    "Nothing has been requested and nothing will run.",
                tone: "neutral",
            }
        case "awaiting_approval":
        case "pending":
            return {
                label: "AWAITING APPROVAL",
                meaning: "A named human must decide. Nothing runs until one does.",
                tone: "open",
            }
        case "granted":
        case "approved":
            return {
                label: "APPROVED",
                meaning:
                    "A named human approved this exact action, bound to its action " +
                    "digest. Approved is not executed.",
                tone: "established",
            }
        case "denied":
        case "rejected":
            return {
                label: "REJECTED",
                meaning: "A human refused this action. It cannot run.",
                tone: "excluded",
            }
        case "withdrawn":
            return {
                label: "WITHDRAWN",
                meaning: "The approval was revoked. It authorizes nothing.",
                tone: "excluded",
            }
        case "expired":
            return {
                label: "EXPIRED",
                meaning:
                    "The approval passed its expiry. Nobody changed their mind — " +
                    "it simply no longer authorizes anything.",
                tone: "aged",
            }
        case "executing":
            return {
                label: "EXECUTING",
                meaning:
                    "The governed chain accepted the action. What happened in the " +
                    "world is NOT yet established.",
                tone: "open",
            }
        case "outcome_established":
            return {
                label: "OUTCOME ESTABLISHED",
                meaning:
                    "An INDEPENDENT World observation says what the world now looks " +
                    "like. This is not the worker's own report of itself.",
                tone: "established",
            }
        case "verified":
            return {
                label: "VERIFIED",
                meaning: "Assurance independently verified the outcome.",
                tone: "established",
            }
        case "insufficient_evidence":
            return {
                label: "INSUFFICIENT EVIDENCE",
                meaning:
                    "Assurance looked and the evidence did not settle whether the " +
                    "remediation worked. Not a failure — an honest 'we do not know'.",
                tone: "insufficient",
            }
        case "refused":
            return {
                label: "REFUSED",
                meaning:
                    "The governed chain refused this action, so nothing was done to " +
                    "the world. A refusal is a decision, not a malfunction.",
                tone: "excluded",
            }
        case "failed":
            return {
                label: "FAILED",
                meaning:
                    "The action could not complete. What reached the world is " +
                    "UNKNOWN until it is observed — this does not mean nothing happened.",
                tone: "disputed",
            }
        default:
            return {
                label: "NOT STARTED",
                meaning: "This stage has not been reached.",
                tone: "neutral",
            }
    }
}

/** How an approval stands right now, expiry included. */
export function readApproval(
    state: string | null | undefined,
    expired: boolean,
): Reading {
    if (expired && ["granted", "pending"].includes(normalise(state))) {
        return readStage("expired")
    }
    return readStage(state)
}
