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


/**
 * Why a caller may not act on a specific approval — Phase 10.7.
 *
 * Each reason names the dimension that failed. "Forbidden" would leave an
 * operator unable to tell a wrong capability from a wrong environment from a
 * risk ceiling, which are three different grants to go and ask for.
 *
 * Every one of these is the server's own reason code, rendered. The client
 * derives none of them.
 */
export function readScopeRefusal(reason: string | null | undefined): Reading {
    switch (normalise(reason)) {
        case "scoped_grant_matched":
        case "approver_authority_granted":
            return {
                label: "IN SCOPE",
                meaning: "Your grant covers this capability and environment.",
                tone: "established",
            }
        case "out_of_scope_capability":
            return {
                label: "OUT OF SCOPE — CAPABILITY",
                meaning:
                    "You hold a grant, and not for this capability. Grants name " +
                    "one capability each; there is no wildcard.",
                tone: "excluded",
            }
        case "out_of_scope_environment":
            return {
                label: "OUT OF SCOPE — ENVIRONMENT",
                meaning:
                    "Your grant is for a different environment than the one this " +
                    "action was raised in.",
                tone: "excluded",
            }
        case "risk_exceeds_grant_ceiling":
            return {
                label: "ABOVE YOUR RISK CEILING",
                meaning:
                    "This action's declared risk is higher than your grant " +
                    "allows. The platform derives the risk from the capability " +
                    "contract — it is not something this page or you can set.",
                tone: "excluded",
            }
        case "grant_is_not_scoped":
            return {
                label: "GRANT NOT SCOPED",
                meaning:
                    "Your grant names no capability and no environment. That form " +
                    "no longer confers authority; it must be re-issued with scope.",
                tone: "absent",
            }
        case "no_executor_authority":
            return {
                label: "NO EXECUTION AUTHORITY",
                meaning:
                    "Approving and executing are different acts with different " +
                    "grants. You may hold one without the other.",
                tone: "absent",
            }
        case "no_approver_authority":
            return {
                label: "NO APPROVAL AUTHORITY",
                meaning: "You hold no approver grant in this tenant.",
                tone: "absent",
            }
        case "separation_of_duties":
            return {
                label: "YOU REQUESTED THIS",
                meaning:
                    "The person who asks for an irreversible action is never the " +
                    "person who allows it.",
                tone: "excluded",
            }
        default:
            return {
                label: (reason || "NOT PERMITTED").toUpperCase().replace(/_/g, " "),
                meaning: `Reported by the platform as "${reason}".`,
                tone: "neutral",
            }
    }
}
