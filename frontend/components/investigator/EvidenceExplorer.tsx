"use client"

import { readSourceStatus } from "@/lib/investigator/epistemic"
import type { EvidenceRef } from "@/lib/investigator/types"
import EpistemicBadge from "./EpistemicBadge"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Empty } from "./LoadState"

/**
 * Evidence, with enough of itself visible to be argued with.
 *
 * A list of observation ids is not an evidence explorer: a responder cannot
 * check a claim they cannot see. Each row therefore carries what was observed,
 * which instrument observed it, that instrument's lineage, and **both** of its
 * clocks.
 *
 * A reference that could not be resolved is shown as unresolved rather than
 * omitted. Dropping it would silently shrink the evidence, which reads as
 * "there was less evidence" rather than "something could not be read".
 */

function Lineage({ evidence }: { evidence: EvidenceRef }) {
    const lineage = evidence.lineage
    if (!lineage) return null
    return (
        <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
            <span className="font-semibold">Lineage: </span>
            {lineage.origin_known ? (
                <>
                    origin <span className="font-mono">{lineage.origin_id}</span>
                    {lineage.relation ? ` (${lineage.relation})` : ""}
                </>
            ) : (
                <>
                    UNKNOWN — this source&rsquo;s origin is not established, so its
                    independence from the others cannot be proven.
                </>
            )}
        </p>
    )
}

export default function EvidenceExplorer({ evidence }: { evidence: EvidenceRef[] }) {
    const unresolved = evidence.filter((e) => !e.resolved).length
    return (
        <Panel
            title="Evidence"
            provenance="world"
            actions={
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {evidence.length} referenced
                    {unresolved > 0 ? ` · ${unresolved} unresolved` : ""}
                </span>
            }
        >
            {evidence.length === 0 ? (
                <Empty>
                    This investigation cites no observations yet. No evidence is not the
                    same as evidence of nothing.
                </Empty>
            ) : (
                <ul className="space-y-3">
                    {evidence.map((e) => (
                        <li
                            key={e.observation_id}
                            className="rounded-lg border p-3"
                            style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                        >
                            {!e.resolved ? (
                                <>
                                    <p className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>
                                        {e.observation_id}
                                    </p>
                                    <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                                        This reference could not be resolved to an observation for
                                        this tenant. It is listed because omitting it would understate
                                        what the investigation cited.
                                    </p>
                                </>
                            ) : (
                                <>
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                        <p className="min-w-0 text-sm" style={{ color: "var(--text-primary)" }}>
                                            <span className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                                                {e.subject_ref}
                                            </span>
                                            <span className="mx-1" style={{ color: "var(--text-muted)" }}>
                                                ·
                                            </span>
                                            <span className="font-semibold">{e.predicate}</span>
                                            {e.value !== null && (
                                                <>
                                                    <span className="mx-1" style={{ color: "var(--text-muted)" }}>
                                                        =
                                                    </span>
                                                    <span className="font-mono">{e.value}</span>
                                                </>
                                            )}
                                        </p>
                                        {e.status && <EpistemicBadge reading={readSourceStatus(e.status)} size="sm" />}
                                    </div>

                                    <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                                        <span className="font-semibold">Source: </span>
                                        {e.source_ref ?? "unattributed"}
                                        {e.source_kind ? ` (${e.source_kind})` : ""}
                                        {e.authority_tier ? ` · authority tier ${e.authority_tier}` : ""}
                                    </p>

                                    <Lineage evidence={e} />

                                    {/* Two clocks, side by side and separately
                                        labelled. Neither is ever shown alone. */}
                                    <div className="mt-2 flex flex-wrap gap-6">
                                        <TemporalStamp clock="observed" value={e.observed_at} />
                                        <TemporalStamp clock="retrieved" value={e.retrieved_at} />
                                    </div>

                                    <p className="mt-2 font-mono text-[10px]" style={{ color: "var(--text-muted)" }}>
                                        {e.observation_id}
                                        {e.execution_ref ? ` · acquired by ${e.execution_ref}` : ""}
                                    </p>
                                </>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    )
}
