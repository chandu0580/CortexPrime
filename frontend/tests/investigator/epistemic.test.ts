import { describe, expect, it } from "vitest"

import {
    readConclusion,
    readCorroboration,
    readEpistemicStatus,
    readFreshness,
    readHypothesisStatus,
    readSourceStatus,
    readVerdict,
    TONE_STYLE,
} from "@/lib/investigator/epistemic"

/**
 * These tests exist because the failure they guard against is silent.
 *
 * Nothing crashes when a UI renders STALE as "unavailable" or
 * INSUFFICIENT_EVIDENCE as a red failure chip — the page looks fine, and the
 * distinction Phase 7-9 spent four phases protecting is gone. So the mapping is
 * asserted directly, in the one module that owns it.
 */

const FALSEY = ["false", "no", "not ", "failed", "failure", "error", "invalid"]

function assertNeverReadsAsFalse(label: string, meaning: string) {
    const text = label.toLowerCase()
    for (const word of ["false", "failed", "error"]) {
        expect(text, `"${label}" must not read as ${word}`).not.toContain(word)
    }
    // The meaning may *mention* false only to deny it.
    if (meaning.toLowerCase().includes("false")) {
        expect(meaning.toLowerCase()).toMatch(/not (the same as |)false|never false|is not false/)
    }
}

describe("epistemic states are never collapsed into false", () => {
    it("UNKNOWN is its own state and says it is not false", () => {
        const reading = readEpistemicStatus("unknown")
        expect(reading.label).toBe("UNKNOWN")
        expect(reading.tone).toBe("absent")
        expect(reading.meaning).toMatch(/not the same as false/i)
        assertNeverReadsAsFalse(reading.label, reading.meaning)
    })

    it("STALE is aged evidence, not a failure and not false", () => {
        const reading = readEpistemicStatus("stale")
        expect(reading.label).toBe("STALE")
        expect(reading.tone).toBe("aged")
        expect(reading.meaning).toMatch(/earlier moment/i)
        expect(reading.meaning).toMatch(/not the same as false/i)
    })

    it("CONFLICTED preserves both readings and is not an error", () => {
        const reading = readEpistemicStatus("conflicted")
        expect(reading.label).toBe("CONFLICTED")
        expect(reading.tone).toBe("disputed")
        expect(reading.meaning).toMatch(/preserved/i)
        assertNeverReadsAsFalse(reading.label, reading.meaning)
    })

    it("an unrecognised status is passed through, never guessed at", () => {
        const reading = readEpistemicStatus("something_new")
        expect(reading.label).toBe("SOMETHING_NEW")
        expect(reading.tone).toBe("neutral")
    })
})

describe("INSUFFICIENT_EVIDENCE is not a failure", () => {
    it("as an Assurance verdict", () => {
        const reading = readVerdict("insufficient_evidence")
        expect(reading.label).toBe("INSUFFICIENT EVIDENCE")
        expect(reading.tone).toBe("insufficient")
        expect(reading.meaning).toMatch(/not a failure/i)
        for (const word of FALSEY) {
            expect(reading.label.toLowerCase()).not.toContain(word)
        }
    })

    it("as an investigation conclusion", () => {
        const reading = readConclusion("insufficient_evidence")
        expect(reading.label).toBe("INSUFFICIENT EVIDENCE")
        expect(reading.meaning).toMatch(/we do not know/i)
    })

    it("UNRESOLVED is explicitly not a system failure", () => {
        expect(readConclusion("unresolved").meaning).toMatch(/not a failure/i)
    })

    it("a missing conclusion reads as in progress, not as a blank", () => {
        expect(readConclusion(null).label).toBe("IN PROGRESS")
        expect(readConclusion(undefined).label).toBe("IN PROGRESS")
    })
})

describe("corroboration cannot be read as independent verification", () => {
    it("CORRELATED says in words that it is not independent", () => {
        const reading = readCorroboration("correlated")
        expect(reading.label).toContain("NOT INDEPENDENT")
        expect(reading.meaning).toMatch(/same lineage origin/i)
        expect(reading.meaning).toMatch(/not confirmation/i)
        expect(reading.label).not.toMatch(/^INDEPENDENT$/)
    })

    it("INDEPENDENT is the only level that claims independence", () => {
        const independent = readCorroboration("independent")
        expect(independent.label).toBe("INDEPENDENT")
        expect(independent.meaning).toMatch(/distinct, known lineage origins/i)

        for (const level of ["correlated", "indeterminate", "single", "contradicted", "insufficient"]) {
            expect(readCorroboration(level).label).not.toBe("INDEPENDENT")
        }
    })

    it("INDETERMINATE refuses to assume independence", () => {
        const reading = readCorroboration("indeterminate")
        expect(reading.label).toBe("INDEPENDENCE UNPROVEN")
        expect(reading.meaning).toMatch(/cannot be proven/i)
    })

    it("SINGLE says repeated readings add no independence", () => {
        expect(readCorroboration("single").meaning).toMatch(/no independence/i)
    })
})

describe("source status keeps empty, unavailable and not-configured apart", () => {
    it("RETURNED_EMPTY is a real observation", () => {
        const reading = readSourceStatus("returned_empty")
        expect(reading.label).toBe("RETURNED EMPTY")
        expect(reading.meaning).toMatch(/genuinely found nothing/i)
        expect(reading.meaning).toMatch(/not a failure to observe/i)
    })

    it("UNAVAILABLE is not evidence of absence", () => {
        const reading = readSourceStatus("unavailable")
        expect(reading.meaning).toMatch(/not evidence of absence/i)
        expect(reading.label).not.toBe(readSourceStatus("returned_empty").label)
    })

    it("NOT_CONFIGURED is distinct from both", () => {
        const labels = new Set([
            readSourceStatus("returned_empty").label,
            readSourceStatus("unavailable").label,
            readSourceStatus("not_configured").label,
        ])
        expect(labels.size).toBe(3)
    })
})

describe("hypotheses", () => {
    it("RULED OUT is about this investigation's evidence, not about the world", () => {
        const reading = readHypothesisStatus("refuted")
        expect(reading.label).toBe("RULED OUT")
        expect(reading.meaning).toMatch(/statement about the evidence/i)
    })

    it("SUPPORTED does not claim verification", () => {
        expect(readHypothesisStatus("supported").meaning).toMatch(/support is not verification/i)
    })
})

describe("freshness", () => {
    it("STALE explains it was not refuted", () => {
        expect(readFreshness("stale").meaning).toMatch(/was not refuted/i)
    })
})

describe("no invented certainty anywhere in the vocabulary", () => {
    const readers = [
        readEpistemicStatus, readVerdict, readHypothesisStatus,
        readCorroboration, readFreshness, readConclusion, readSourceStatus,
    ]
    const inputs = [
        "affirmed", "unknown", "stale", "conflicted", "supported", "unsupported",
        "insufficient_evidence", "refuted", "open", "independent", "correlated",
        "indeterminate", "single", "contradicted", "fresh", "resolved",
        "unresolved", "returned_data", "returned_empty", "unavailable", null,
    ]

    it("emits no percentage, probability or confidence score", () => {
        for (const reader of readers) {
            for (const input of inputs) {
                const { label, meaning } = reader(input)
                const text = `${label} ${meaning}`
                expect(text).not.toMatch(/\d+\s*%/)
                expect(text.toLowerCase()).not.toMatch(/\bconfidence\b/)
                expect(text.toLowerCase()).not.toMatch(/\bprobability\b/)
                expect(text.toLowerCase()).not.toMatch(/\blikelihood\b/)
            }
        }
    })

    it("every tone is a defined epistemic tone, never success/warning/error", () => {
        const allowed = new Set(Object.keys(TONE_STYLE))
        expect(allowed.has("success")).toBe(false)
        expect(allowed.has("error")).toBe(false)
        expect(allowed.has("warning")).toBe(false)
        for (const reader of readers) {
            for (const input of inputs) {
                expect(allowed.has(reader(input).tone)).toBe(true)
            }
        }
    })

    it("every reading carries a non-empty textual label", () => {
        for (const reader of readers) {
            for (const input of inputs) {
                expect(reader(input).label.trim().length).toBeGreaterThan(0)
            }
        }
    })
})
