import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import EpistemicBadge from "@/components/investigator/EpistemicBadge"
import EvidenceExplorer from "@/components/investigator/EvidenceExplorer"
import HypothesisPanel from "@/components/investigator/HypothesisPanel"
import AssurancePanel from "@/components/investigator/AssurancePanel"
import HistoricalExperience from "@/components/investigator/HistoricalExperience"
import TemporalStamp from "@/components/investigator/TemporalStamp"
import { readEpistemicStatus, readVerdict } from "@/lib/investigator/epistemic"
import { productGet } from "@/lib/product-api"
import type { EvidenceRef, Hypothesis } from "@/lib/investigator/types"

function wrap(ui: React.ReactElement) {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

afterEach(() => {
    vi.unstubAllGlobals()
})

describe("epistemic state is textual, not colour-only", () => {
    it("renders the state name as readable text", () => {
        render(<EpistemicBadge reading={readEpistemicStatus("stale")} />)
        // Present in the accessibility tree, so it survives greyscale and a
        // screen reader — the requirement colour alone cannot meet.
        expect(screen.getByText("STALE")).toBeInTheDocument()
    })

    it("carries the explanation as well as the label", () => {
        render(<EpistemicBadge reading={readEpistemicStatus("conflicted")} explain />)
        expect(screen.getByText(/Sources disagree/i)).toBeInTheDocument()
    })
})

describe("timestamps always say which clock they came from", () => {
    it("labels an observation time as a world time", () => {
        render(<TemporalStamp clock="observed" value="2026-09-05T10:00:00+00:00" />)
        expect(screen.getByText("World observed at")).toBeInTheDocument()
    })

    it("labels a ledger time as a ledger time, not as an event time", () => {
        render(<TemporalStamp clock="recorded" value="2026-09-05T10:04:00+00:00" />)
        expect(screen.getByText("Recorded in ledger at")).toBeInTheDocument()
        expect(screen.queryByText("World observed at")).not.toBeInTheDocument()
    })

    it("says so rather than rendering an empty slot when there is no time", () => {
        render(<TemporalStamp clock="observed" value={null} />)
        expect(screen.getByText("not recorded")).toBeInTheDocument()
    })
})

describe("the differential keeps every competitor visible", () => {
    const hypotheses: Hypothesis[] = [
        {
            hypothesis_id: "h-config", statement: "Bad configuration", subject_ref: "s",
            status: "refuted", temporal_fit: "unknown", evidence_for: [],
            evidence_against: ["obs-1"], missing_evidence: [], contradiction_refs: [],
            lineage_origins: [], authority: null, created_by: "platform",
            unresolved_reason: null, would_support: null, would_contradict: null,
            discriminates_from: [],
        },
        {
            hypothesis_id: "h-startup", statement: "Startup failure", subject_ref: "s",
            status: "open", temporal_fit: "unknown", evidence_for: [],
            evidence_against: [], missing_evidence: ["exit code"], contradiction_refs: [],
            lineage_origins: [], authority: null, created_by: "platform",
            unresolved_reason: "no discriminating observation acquired yet",
            would_support: null, would_contradict: null, discriminates_from: [],
        },
    ]

    it("shows a ruled-out hypothesis rather than hiding it", () => {
        render(<HypothesisPanel hypotheses={hypotheses} />)
        expect(screen.getByText("Bad configuration")).toBeInTheDocument()
        expect(screen.getByText("RULED OUT")).toBeInTheDocument()
    })

    it("shows missing evidence as an explicit gap", () => {
        render(<HypothesisPanel hypotheses={hypotheses} />)
        expect(screen.getByText(/Missing evidence — not yet observed/i)).toBeInTheDocument()
        expect(screen.getByText("exit code")).toBeInTheDocument()
    })

    it("says why a hypothesis is still unresolved", () => {
        render(<HypothesisPanel hypotheses={hypotheses} />)
        expect(screen.getByText(/no discriminating observation acquired yet/i)).toBeInTheDocument()
    })

    it("an empty differential is not rendered as 'nothing is wrong'", () => {
        render(<HypothesisPanel hypotheses={[]} />)
        expect(screen.getByText(/not a finding that nothing is wrong/i)).toBeInTheDocument()
    })
})

describe("evidence shows both clocks and reports what it could not resolve", () => {
    const evidence: EvidenceRef[] = [
        {
            observation_id: "obs-1", subject_ref: "pod/x", predicate: "restart_count",
            value: "7", status: "returned_data", source_ref: "connector:kubernetes",
            source_kind: "connector", authority_tier: "primary",
            lineage: { source_kind: "connector", source_ref: "connector:prometheus", origin_id: null, relation: null, origin_known: false },
            observed_at: "2026-09-05T10:00:00+00:00",
            retrieved_at: "2026-09-05T10:04:00+00:00",
            execution_ref: "exec-1", trace_ref: null, resolved: true,
        },
        {
            observation_id: "obs-missing", subject_ref: "", predicate: "", value: null,
            status: null, source_ref: null, source_kind: null, authority_tier: null,
            lineage: null, observed_at: null, retrieved_at: null,
            execution_ref: null, trace_ref: null, resolved: false,
        },
    ]

    it("renders the observed and retrieved times under different labels", () => {
        render(<EvidenceExplorer evidence={evidence} />)
        expect(screen.getByText("World observed at")).toBeInTheDocument()
        expect(screen.getByText("CortexPrime learned at")).toBeInTheDocument()
    })

    it("lists an unresolved reference instead of dropping it", () => {
        render(<EvidenceExplorer evidence={evidence} />)
        expect(screen.getByText("obs-missing")).toBeInTheDocument()
        expect(screen.getByText(/could not be resolved/i)).toBeInTheDocument()
        expect(screen.getByText(/1 unresolved/)).toBeInTheDocument()
    })

    it("says plainly when a source's lineage is unknown", () => {
        render(<EvidenceExplorer evidence={evidence} />)
        expect(screen.getByText(/independence from the others cannot be proven/i)).toBeInTheDocument()
    })
})

describe("assurance", () => {
    it("states that an unverified investigation is unverified", async () => {
        vi.stubGlobal("fetch", vi.fn(async () =>
            new Response(JSON.stringify({ investigation_ref: "i-1", items: [], count: 0, note: "none yet" }),
                { status: 200, headers: { "Content-Type": "application/json" } })))

        wrap(<AssurancePanel investigationRef="i-1" assuranceVerified={false} />)
        expect(await screen.findByText(/has NOT verified/i)).toBeInTheDocument()
        expect(screen.getByText(/support and verification are separate gates/i)).toBeInTheDocument()
    })

    it("shows no percentage for a supported verdict", async () => {
        vi.stubGlobal("fetch", vi.fn(async () =>
            new Response(JSON.stringify({
                investigation_ref: "i-1", count: 1, note: "",
                items: [{
                    verification_id: "v-1", verdict: "supported", subject_ref: "pod/x",
                    procedure_ref: "check:restart-observed/1",
                    verifier_ref: "assurance:world-verifier/1",
                    verifier_reasoning_path: "assurance-path/1",
                    rationale: "restart observed independently", verified_at: "2026-09-05T10:05:00+00:00",
                    evidence_refs: ["obs-1"],
                }],
            }), { status: 200, headers: { "Content-Type": "application/json" } })))

        const { container } = wrap(<AssurancePanel investigationRef="i-1" assuranceVerified />)
        await screen.findByText("SUPPORTED")
        expect(screen.getByText(/assurance:world-verifier\/1/)).toBeInTheDocument()
        expect(container.textContent ?? "").not.toMatch(/\d+\s*%/)
        expect(container.textContent ?? "").not.toMatch(/confidence/i)
    })

    it("keeps INSUFFICIENT EVIDENCE distinct from UNSUPPORTED", () => {
        expect(readVerdict("insufficient_evidence").label).not.toBe(readVerdict("unsupported").label)
        expect(readVerdict("insufficient_evidence").tone).not.toBe(readVerdict("unsupported").tone)
    })
})

describe("historical experience is never presented as current truth", () => {
    it("carries an explicit disclaimer and its own heading", async () => {
        vi.stubGlobal("fetch", vi.fn(async () =>
            new Response(JSON.stringify({ items: [], count: 0, limit: 50, state: "completed", note: "" }),
                { status: 200, headers: { "Content-Type": "application/json" } })))

        wrap(<HistoricalExperience subjectRef="pod/x" excludeRef="i-1" />)
        await waitFor(() =>
            expect(screen.getByText("HISTORICAL EXPERIENCE")).toBeInTheDocument())
        expect(screen.getByText(/do not establish what is true now/i)).toBeInTheDocument()
    })
})

describe("the client is structurally incapable of asserting a tenant", () => {
    it("refuses to send a tenant parameter", async () => {
        vi.stubGlobal("fetch", vi.fn())
        await expect(
            productGet("/api/v1/investigations", { tenant_id: "someone-else" }),
        ).rejects.toThrow(/must never send a tenant/i)
        expect(fetch).not.toHaveBeenCalled()
    })

    it("sends credentials so the HttpOnly session cookie is used", async () => {
        const fetchMock = vi.fn(async () =>
            new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }))
        vi.stubGlobal("fetch", fetchMock)

        await productGet("/api/v1/investigations")
        const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
        expect(init.credentials).toBe("include")
        expect(init.method).toBe("GET")
        // No Authorization header is constructed here: the token is HttpOnly
        // and this code cannot read it.
        expect(JSON.stringify(init.headers)).not.toMatch(/authorization/i)
    })
})
