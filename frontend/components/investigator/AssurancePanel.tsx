"use client"

import { useAssurance } from "@/hooks/queries/useInvestigator"
import { readVerdict } from "@/lib/investigator/epistemic"
import EpistemicBadge from "./EpistemicBadge"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Empty, Loading, RequestFailure } from "./LoadState"

/**
 * Independent verification, as the verifier recorded it.
 *
 * This component computes nothing. It has no rule that turns evidence into a
 * verdict, no aggregation across verifications, and no summary line saying how
 * verified the investigation is overall — a frontend that derives a verdict is
 * a second Assurance, and the one in the backend is the only one allowed to
 * exist.
 *
 * There is also no percentage. "100% verified" is not a thing Assurance can
 * say, so it is not a thing this screen can display.
 */

export default function AssurancePanel({
    investigationRef,
    assuranceVerified,
}: {
    investigationRef: string
    assuranceVerified: boolean
}) {
    const query = useAssurance(investigationRef)

    return (
        <Panel title="Assurance" provenance="assurance">
            <p
                className="mb-3 rounded border px-3 py-2 text-xs leading-relaxed"
                style={{
                    borderColor: "var(--border-strong)",
                    background: "var(--surface-raised)",
                    color: "var(--text-secondary)",
                }}
            >
                {assuranceVerified
                    ? "Assurance has independently verified this investigation's conclusion."
                    : "Assurance has NOT verified this investigation's conclusion. A hypothesis " +
                      "supported by world evidence is not a verified one — support and " +
                      "verification are separate gates."}
            </p>

            {query.isPending && <Loading label="verifications" />}
            {query.isError && <RequestFailure error={query.error} label="verifications" />}

            {query.data && query.data.items.length === 0 && (
                <Empty>{query.data.note}</Empty>
            )}

            {query.data && query.data.items.length > 0 && (
                <ul className="space-y-3">
                    {query.data.items.map((verification) => (
                        <li
                            key={verification.verification_id}
                            className="rounded-lg border p-3"
                            style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                        >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <p className="min-w-0 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                                    {verification.subject_ref}
                                    {verification.procedure_ref ? ` · ${verification.procedure_ref}` : ""}
                                </p>
                                <EpistemicBadge reading={readVerdict(verification.verdict)} size="sm" />
                            </div>

                            <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                                {readVerdict(verification.verdict).meaning}
                            </p>

                            {verification.rationale && (
                                <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                                    <span className="font-semibold">Rationale: </span>
                                    {verification.rationale}
                                </p>
                            )}

                            <p className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                                <span className="font-semibold">Verified by: </span>
                                {/* Shown so independence can be checked rather
                                    than assumed. */}
                                {verification.verifier_ref ?? "verifier not recorded"}
                                {verification.verifier_reasoning_path
                                    ? ` (reasoning path ${verification.verifier_reasoning_path})`
                                    : ""}
                            </p>

                            <div className="mt-2">
                                <TemporalStamp clock="recorded" value={verification.verified_at} />
                            </div>

                            {verification.evidence_refs.length > 0 && (
                                <div className="mt-2">
                                    <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                                        Cited evidence ({verification.evidence_refs.length})
                                    </span>
                                    <ul className="mt-1 space-y-0.5">
                                        {verification.evidence_refs.map((ref) => (
                                            <li key={ref} className="font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                                {ref}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    )
}
