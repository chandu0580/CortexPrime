/**
 * The epistemic vocabulary of the workspace.
 *
 * This module exists so that the mapping from a backend state to what a human
 * reads happens in exactly one place, and can be tested. Everything Phase 7–9
 * protected — UNKNOWN is not FALSE, STALE is not FALSE, CONFLICTED is not
 * FALSE, INSUFFICIENT_EVIDENCE is not a failure — is protected or lost here.
 *
 * Two rules it enforces
 * ---------------------
 * 1. **The state name is always textual.** `label` is rendered as words. Colour
 *    is decoration on top of a label that already says the whole thing, so the
 *    display survives greyscale, colour-blindness and a screen reader.
 * 2. **The tone vocabulary is not success/warning/error.** The existing
 *    `StatusPill` offers exactly those, and they are wrong here: a stale
 *    observation is not a warning about a malfunction, and a conflict is not an
 *    error. The tones below describe *epistemic standing*, and the module maps
 *    nothing onto "failed".
 */

/**
 * How a statement stands, epistemically. Deliberately NOT
 * success | warning | error.
 */
export type Tone =
    /** Established on evidence. */
    | "established"
    /** Nothing is known. Absence of knowledge, not knowledge of absence. */
    | "absent"
    /** True of an earlier moment; not false now, just not current. */
    | "aged"
    /** Sources disagree and nothing has settled it. Both readings survive. */
    | "disputed"
    /** The evidence did not settle the question. Not a negative answer. */
    | "insufficient"
    /** Ruled out by this investigation's evidence. */
    | "excluded"
    /** Still competing; no verdict yet. */
    | "open"
    /** Descriptive only. */
    | "neutral"

export interface Reading {
    /** What is shown. Always words, never a colour alone. */
    label: string
    /** One sentence a responder can act on, spelling out what it is NOT. */
    meaning: string
    tone: Tone
}

function normalise(value: string | null | undefined): string {
    return (value ?? "").trim().toLowerCase().replace(/[\s-]+/g, "_")
}

const NEVER_FALSE =
    "This is not the same as false — it is a different answer."

/** World / observation epistemic status. */
export function readEpistemicStatus(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "affirmed":
        case "known":
            return {
                label: "AFFIRMED",
                meaning: "Established by admissible evidence at the time asked about.",
                tone: "established",
            }
        case "unknown":
            return {
                label: "UNKNOWN",
                meaning: `Nothing has been observed that settles this. ${NEVER_FALSE}`,
                tone: "absent",
            }
        case "stale":
            return {
                label: "STALE",
                meaning:
                    "The evidence is older than its freshness horizon. It describes " +
                    `an earlier moment and may still be true. ${NEVER_FALSE}`,
                tone: "aged",
            }
        case "conflicted":
            return {
                label: "CONFLICTED",
                meaning:
                    "Sources disagree and no authority settled it. Every competing " +
                    `value is preserved below. ${NEVER_FALSE}`,
                tone: "disputed",
            }
        case "retracted":
            return {
                label: "RETRACTED",
                meaning: "The supporting evidence was withdrawn.",
                tone: "absent",
            }
        default:
            return {
                label: (raw || "UNKNOWN").toUpperCase(),
                meaning: `Reported by the platform as "${raw}". ${NEVER_FALSE}`,
                tone: "neutral",
            }
    }
}

/** Assurance verdicts. */
export function readVerdict(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "supported":
            return {
                label: "SUPPORTED",
                meaning:
                    "An independent verifier found admissible evidence for this. " +
                    "This is a verdict about the evidence, not a percentage.",
                tone: "established",
            }
        case "unsupported":
            return {
                label: "UNSUPPORTED",
                meaning:
                    "The verifier looked and the evidence did not support the claim.",
                tone: "disputed",
            }
        case "insufficient_evidence":
            return {
                label: "INSUFFICIENT EVIDENCE",
                meaning:
                    "The evidence did not settle the question. This is not a " +
                    "failure of the investigation and not a negative verdict — " +
                    "it is an honest 'we do not know'.",
                tone: "insufficient",
            }
        default:
            return {
                label: (raw || "UNKNOWN").toUpperCase(),
                meaning: `Recorded by Assurance as "${raw}".`,
                tone: "neutral",
            }
    }
}

/** Hypothesis standing within a differential. */
export function readHypothesisStatus(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "supported":
            return {
                label: "SUPPORTED",
                meaning:
                    "Backed by world evidence. Support is not verification, and " +
                    "the alternatives below are not thereby false.",
                tone: "established",
            }
        case "refuted":
        case "eliminated":
            return {
                label: "RULED OUT",
                meaning:
                    "Excluded by this investigation's evidence. That is a " +
                    "statement about the evidence, not proof it could never happen.",
                tone: "excluded",
            }
        case "open":
            return {
                label: "OPEN",
                meaning: "Still competing. No evidence has discriminated it yet.",
                tone: "open",
            }
        case "unresolved":
            return {
                label: "UNRESOLVED",
                meaning:
                    "Has evidence but nothing that discriminates it from the others.",
                tone: "open",
            }
        default:
            return {
                label: (raw || "OPEN").toUpperCase(),
                meaning: `Recorded by the platform as "${raw}".`,
                tone: "neutral",
            }
    }
}

/**
 * Corroboration — the single most misreadable value in the product.
 *
 * CORRELATED means two instruments agreed while sharing one origin. Displaying
 * that as "independently verified" is the exact error Phase 9.4 built lineage
 * tracking to prevent, so the label says the opposite in words.
 */
export function readCorroboration(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "independent":
            return {
                label: "INDEPENDENT",
                meaning:
                    "Two or more sources with distinct, known lineage origins agree. " +
                    "This is the only level that claims proven independence.",
                tone: "established",
            }
        case "correlated":
            return {
                label: "CORRELATED — NOT INDEPENDENT",
                meaning:
                    "The agreeing sources resolve to the SAME lineage origin, so " +
                    "they are one independent unit, not several. Agreement here " +
                    "is not confirmation.",
                tone: "aged",
            }
        case "indeterminate":
            return {
                label: "INDEPENDENCE UNPROVEN",
                meaning:
                    "Distinct sources agree, but at least one has unknown lineage, " +
                    "so independence cannot be proven. Not treated as independent.",
                tone: "absent",
            }
        case "single":
            return {
                label: "SINGLE SOURCE",
                meaning:
                    "Exactly one source supports this value. Repeated readings from " +
                    "that source add no independence.",
                tone: "open",
            }
        case "contradicted":
            return {
                label: "CONTRADICTED",
                meaning: "Sources disagree; there is no single corroborated value.",
                tone: "disputed",
            }
        case "insufficient":
            return {
                label: "NO EVIDENCE IN WINDOW",
                meaning: "No evidence covers the instant asked about.",
                tone: "absent",
            }
        default:
            return {
                label: (raw || "UNKNOWN").toUpperCase(),
                meaning: `Assessed by the platform as "${raw}".`,
                tone: "neutral",
            }
    }
}

/** Freshness. STALE is a state of the evidence, never a transport failure. */
export function readFreshness(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "fresh":
            return {
                label: "FRESH",
                meaning: "Within its freshness horizon.",
                tone: "established",
            }
        case "stale":
            return {
                label: "STALE",
                meaning:
                    "Older than its horizon. It describes an earlier moment and " +
                    "was not refuted — it simply has not been re-observed.",
                tone: "aged",
            }
        case "unknown":
            return {
                label: "AGE UNKNOWN",
                meaning: "There is no horizon configured to judge this against.",
                tone: "absent",
            }
        default:
            return {
                label: (raw || "AGE UNKNOWN").toUpperCase(),
                meaning: `Reported as "${raw}".`,
                tone: "neutral",
            }
    }
}

/** Investigation conclusion kinds. */
export function readConclusion(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "resolved":
            return {
                label: "RESOLVED",
                meaning:
                    "One hypothesis is affirmed on admissible evidence. It does " +
                    "not claim the remaining alternatives are false.",
                tone: "established",
            }
        case "unresolved":
            return {
                label: "UNRESOLVED",
                meaning:
                    "Investigated; no hypothesis affirmed. This is not a failure " +
                    "of the system.",
                tone: "open",
            }
        case "insufficient_evidence":
            return {
                label: "INSUFFICIENT EVIDENCE",
                meaning:
                    "Not enough admissible evidence to adjudicate — an honest " +
                    "'we do not know', not a negative finding.",
                tone: "insufficient",
            }
        case "conflicted":
            return {
                label: "CONFLICTED",
                meaning:
                    "Competing evidence, unresolved by authority. Both paths kept.",
                tone: "disputed",
            }
        case "escalated":
            return {
                label: "ESCALATED",
                meaning: "Handed to a human for adjudication.",
                tone: "open",
            }
        case "blocked":
            return {
                label: "BLOCKED",
                meaning: "A required governed read was refused or unavailable.",
                tone: "absent",
            }
        case "failed":
            return {
                label: "FAILED",
                meaning: "The investigation itself could not proceed.",
                tone: "disputed",
            }
        default:
            return {
                label: "IN PROGRESS",
                meaning: "No conclusion has been recorded yet.",
                tone: "open",
            }
    }
}

/** Observation source status. Empty is not unavailable; neither is false. */
export function readSourceStatus(raw: string | null | undefined): Reading {
    switch (normalise(raw)) {
        case "returned_data":
            return { label: "RETURNED DATA", meaning: "The instrument answered with a value.", tone: "established" }
        case "returned_empty":
            return {
                label: "RETURNED EMPTY",
                meaning:
                    "The query succeeded and genuinely found nothing. That is a " +
                    "real observation, not a failure to observe.",
                tone: "open",
            }
        case "unavailable":
            return {
                label: "SOURCE UNAVAILABLE",
                meaning:
                    "The instrument could not be reached. Nothing is known about " +
                    "the world from it — this is not evidence of absence.",
                tone: "absent",
            }
        case "not_configured":
            return {
                label: "NOT CONFIGURED",
                meaning: "No such instrument is configured for this tenant.",
                tone: "absent",
            }
        default:
            return { label: (raw || "UNKNOWN").toUpperCase(), meaning: `Reported as "${raw}".`, tone: "neutral" }
    }
}

/** The platform autonomy ladder. Displayed as a fact; never a control. */
export function readAutonomy(raw: string | null | undefined): Reading {
    const map: Record<string, [string, string]> = {
        a0_observe: ["A0 — OBSERVE", "Ingests signals; takes no investigative action."],
        a1_investigate: ["A1 — INVESTIGATE", "Read-only evidence acquisition. The default."],
        a2_recommend: ["A2 — RECOMMEND", "May produce a differential and propose an action; does not execute."],
        a3_approved_action: ["A3 — APPROVED ACTION", "May execute a specific action, each one human-approved through governance."],
        a4_autonomous: ["A4 — AUTONOMOUS", "Policy-authorised autonomous remediation. Disabled by default."],
    }
    const hit = map[normalise(raw)]
    return {
        label: hit ? hit[0] : (raw || "UNKNOWN").toUpperCase(),
        meaning: hit
            ? `${hit[1]} Set by platform policy — never by a model, and not changeable from this screen.`
            : "Set by platform policy.",
        tone: "neutral",
    }
}

/** Workflow status of an investigation. Descriptive only. */
export function readInvestigationStatus(raw: string | null | undefined): Reading {
    const key = normalise(raw)
    const label = (raw || "unknown").replace(/_/g, " ").toUpperCase()
    if (key === "waiting_for_human") {
        return { label, meaning: "Paused pending a human decision.", tone: "open" }
    }
    if (["completed", "failed", "abandoned"].includes(key)) {
        return { label, meaning: "Terminal — no further transitions.", tone: "neutral" }
    }
    return { label, meaning: "In progress.", tone: "open" }
}

/**
 * The CSS custom properties each tone renders with.
 *
 * Every tone still ships a full text label, so this is emphasis, not meaning.
 */
export const TONE_STYLE: Record<Tone, { fg: string; bg: string; border: string }> = {
    established: { fg: "var(--success)", bg: "var(--success-muted)", border: "var(--success-border)" },
    absent: { fg: "var(--text-muted)", bg: "var(--surface-raised)", border: "var(--border-strong)" },
    aged: { fg: "var(--warning)", bg: "var(--warning-muted)", border: "var(--border-strong)" },
    disputed: { fg: "var(--danger)", bg: "var(--danger-muted)", border: "var(--danger-border)" },
    insufficient: { fg: "var(--info)", bg: "var(--info-muted)", border: "var(--border-strong)" },
    excluded: { fg: "var(--text-muted)", bg: "transparent", border: "var(--border-strong)" },
    open: { fg: "var(--accent-primary)", bg: "var(--accent-muted)", border: "var(--accent-border)" },
    neutral: { fg: "var(--text-secondary)", bg: "var(--surface-raised)", border: "var(--border)" },
}
