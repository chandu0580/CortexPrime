"use client"

import { useState } from "react"

import { readCorroboration, readEpistemicStatus, readFreshness } from "@/lib/investigator/epistemic"
import { useWorldState } from "@/hooks/queries/useInvestigator"
import EpistemicBadge from "./EpistemicBadge"
import EvidenceExplorer from "./EvidenceExplorer"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Loading, RequestFailure } from "./LoadState"

/**
 * Current World state for one subject and predicate.
 *
 * The browser never queries Kubernetes or Prometheus. It asks the Product API,
 * which reads the World Plane — a store of what was already observed through
 * governed execution. Nothing on this screen initiates a read of anything.
 *
 * Everything that qualifies the value is shown next to it: the epistemic
 * status, how old the evidence is, which source had authority, what the losing
 * sources said, and whether the agreeing sources were actually independent.
 * A value shown alone is a value that has been stripped of the reasons it might
 * be wrong.
 */

export default function WorldStatePanel({
    subjectRef,
    defaultPredicate,
}: {
    subjectRef: string
    defaultPredicate: string
}) {
    const [predicate, setPredicate] = useState(defaultPredicate)
    const [applied, setApplied] = useState(defaultPredicate)
    const query = useWorldState(subjectRef, applied)

    return (
        <Panel
            title="World state"
            provenance="world"
            actions={
                <form
                    className="flex items-center gap-2"
                    onSubmit={(event) => {
                        event.preventDefault()
                        setApplied(predicate.trim())
                    }}
                >
                    <label htmlFor="predicate" className="sr-only">
                        Predicate to read
                    </label>
                    <input
                        id="predicate"
                        value={predicate}
                        onChange={(event) => setPredicate(event.target.value)}
                        className="rounded border px-2 py-1 text-xs"
                        style={{
                            borderColor: "var(--border-strong)",
                            background: "var(--surface-raised)",
                            color: "var(--text-primary)",
                        }}
                        placeholder="predicate"
                    />
                    <button
                        type="submit"
                        className="rounded border px-2 py-1 text-xs font-semibold"
                        style={{ borderColor: "var(--accent-border)", color: "var(--accent-primary)" }}
                    >
                        Read
                    </button>
                </form>
            }
        >
            {query.isPending && <Loading label="world state" />}
            {query.isError && <RequestFailure error={query.error} label="world state" />}

            {query.data && (
                <div className="space-y-4">
                    <div>
                        <p className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                            {query.data.subject_ref} · {query.data.predicate}
                        </p>
                        <div className="mt-2 flex flex-wrap items-baseline gap-3">
                            <span className="font-mono text-lg" style={{ color: "var(--text-primary)" }}>
                                {/* No value is a real answer here, and it is
                                    written out rather than left as a blank. */}
                                {query.data.value ?? "no established value"}
                            </span>
                            <EpistemicBadge reading={readEpistemicStatus(query.data.epistemic_status)} />
                        </div>
                        <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                            {readEpistemicStatus(query.data.epistemic_status).meaning}
                        </p>
                    </div>

                    <div className="flex flex-wrap gap-6">
                        <TemporalStamp clock="observed" value={query.data.observed_at} />
                        <TemporalStamp clock="asked" value={query.data.queried_valid_at} />
                        <TemporalStamp clock="read" value={query.data.read_at} />
                    </div>

                    <div
                        className="rounded-lg border p-3"
                        style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                    >
                        <div className="flex flex-wrap items-center gap-3">
                            <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                                Freshness
                            </span>
                            <EpistemicBadge reading={readFreshness(query.data.freshness.state)} size="sm" />
                            {query.data.freshness.age_seconds !== null && (
                                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                                    {Math.round(query.data.freshness.age_seconds)}s old
                                    {query.data.freshness.horizon_seconds !== null &&
                                        ` · horizon ${Math.round(query.data.freshness.horizon_seconds)}s`}
                                </span>
                            )}
                        </div>
                        {query.data.freshness.reason && (
                            <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                                {query.data.freshness.reason}
                            </p>
                        )}
                    </div>

                    <div
                        className="rounded-lg border p-3"
                        style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                    >
                        <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                            Authority — {query.data.authority.status.toUpperCase()}
                        </p>
                        <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                            {query.data.authority.reason || "No authority policy governs this predicate."}
                        </p>
                        {query.data.authority.source_ref && (
                            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                                Settled by <span className="font-mono">{query.data.authority.source_ref}</span>
                                {query.data.authority.tier ? ` (tier ${query.data.authority.tier})` : ""}
                            </p>
                        )}
                        {query.data.authority.alternatives.length > 0 && (
                            <div className="mt-2">
                                <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--warning)" }}>
                                    Competing values retained ({query.data.authority.alternatives.length})
                                </p>
                                <ul className="mt-1 space-y-0.5">
                                    {query.data.authority.alternatives.map((alt, index) => (
                                        <li key={`${alt.source_ref}-${index}`} className="font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                            {alt.value ?? "—"} from {alt.source_ref ?? "unattributed"}
                                            {alt.tier ? ` (tier ${alt.tier})` : ""}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>

                    {query.data.corroboration && (
                        <div
                            className="rounded-lg border p-3"
                            style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                        >
                            <div className="flex flex-wrap items-center gap-3">
                                <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                                    Corroboration
                                </span>
                                <EpistemicBadge reading={readCorroboration(query.data.corroboration.level)} size="sm" />
                            </div>
                            <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                                {readCorroboration(query.data.corroboration.level).meaning}
                            </p>
                            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                                {query.data.corroboration.reason}
                            </p>
                            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                <dt>Agreeing sources</dt>
                                <dd className="font-mono">{query.data.corroboration.independent_sources.join(", ") || "none"}</dd>
                                <dt>Distinct known origins</dt>
                                <dd className="font-mono">{query.data.corroboration.independent_origins.join(", ") || "none"}</dd>
                                <dt>Supporting observations</dt>
                                <dd className="font-mono">{query.data.corroboration.supporting_count}</dd>
                                <dt>Contradicting observations</dt>
                                <dd className="font-mono">{query.data.corroboration.contradicting_count}</dd>
                            </dl>
                            {query.data.corroboration.lineage.length > 0 && (
                                <ul className="mt-2 space-y-0.5">
                                    {query.data.corroboration.lineage.map((lg) => (
                                        <li key={lg.source_ref} className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                                            <span className="font-mono">{lg.source_ref}</span>
                                            {" → "}
                                            {lg.origin_known ? (
                                                <span className="font-mono">{lg.origin_id}</span>
                                            ) : (
                                                <span>UNKNOWN ORIGIN</span>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}

                    <EvidenceExplorer evidence={query.data.evidence} />
                </div>
            )}
        </Panel>
    )
}
