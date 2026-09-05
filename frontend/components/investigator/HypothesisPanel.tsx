"use client"

import { readHypothesisStatus } from "@/lib/investigator/epistemic"
import type { Hypothesis } from "@/lib/investigator/types"
import EpistemicBadge from "./EpistemicBadge"
import Panel from "./Panel"
import { Empty } from "./LoadState"

/**
 * The differential.
 *
 * Every competing explanation stays on screen, including the ruled-out ones.
 * Hiding eliminated hypotheses would turn a differential into an answer, and
 * the whole point of holding a differential is that the remaining alternatives
 * are visible as still-possible rather than quietly dropped.
 *
 * There is no ordering by preference and no score. The engine has neither.
 */

function Refs({ label, refs, tone }: { label: string; refs: string[]; tone: string }) {
    if (!refs.length) return null
    return (
        <div className="mt-2">
            <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: tone }}>
                {label} ({refs.length})
            </span>
            <ul className="mt-1 space-y-0.5">
                {refs.map((ref) => (
                    <li key={ref} className="font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                        {ref}
                    </li>
                ))}
            </ul>
        </div>
    )
}

export default function HypothesisPanel({ hypotheses }: { hypotheses: Hypothesis[] }) {
    return (
        <Panel title="Differential diagnosis" provenance="investigation">
            {hypotheses.length === 0 ? (
                <Empty>
                    No hypotheses have been recorded. That is not a finding that nothing is
                    wrong — it means this investigation has not proposed an explanation yet.
                </Empty>
            ) : (
                <ul className="space-y-4">
                    {hypotheses.map((h) => {
                        const reading = readHypothesisStatus(h.status)
                        return (
                            <li
                                key={h.hypothesis_id}
                                className="rounded-lg border p-3"
                                style={{
                                    borderColor: "var(--border)",
                                    background: "var(--surface-raised)",
                                    // Ruled-out hypotheses stay legible: dimmed
                                    // to de-emphasise, never hidden.
                                    opacity: reading.tone === "excluded" ? 0.72 : 1,
                                }}
                            >
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                    <p className="min-w-0 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                                        {h.statement}
                                    </p>
                                    <EpistemicBadge reading={reading} size="sm" />
                                </div>

                                <p className="mt-1 font-mono text-[11px]" style={{ color: "var(--text-muted)" }}>
                                    {h.hypothesis_id}
                                    {h.created_by ? ` · proposed by ${h.created_by}` : ""}
                                </p>

                                <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                                    {reading.meaning}
                                </p>

                                {h.temporal_fit && (
                                    <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                                        <span className="font-semibold">Temporal fit: </span>
                                        {h.temporal_fit.toUpperCase()}
                                        {h.temporal_fit.toLowerCase() === "unknown" &&
                                            " — the timing has not been established, which is not the same as the timing being wrong."}
                                    </p>
                                )}

                                {h.unresolved_reason && (
                                    <p
                                        className="mt-2 rounded border-l-2 pl-2 text-xs leading-relaxed"
                                        style={{ borderColor: "var(--accent-border)", color: "var(--text-secondary)" }}
                                    >
                                        <span className="font-semibold">Why still unresolved: </span>
                                        {h.unresolved_reason}
                                    </p>
                                )}

                                <Refs label="Supporting evidence" refs={h.evidence_for} tone="var(--success)" />
                                <Refs label="Contradicting evidence" refs={h.evidence_against} tone="var(--danger)" />
                                {/* An explicit gap. Absence of a listed item is
                                    not evidence against the hypothesis. */}
                                <Refs label="Missing evidence — not yet observed" refs={h.missing_evidence} tone="var(--warning)" />
                                <Refs label="Contradictions" refs={h.contradiction_refs} tone="var(--danger)" />

                                {h.would_support && (
                                    <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                                        <span className="font-semibold">Would support: </span>
                                        {h.would_support}
                                    </p>
                                )}
                                {h.would_contradict && (
                                    <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                                        <span className="font-semibold">Would contradict: </span>
                                        {h.would_contradict}
                                    </p>
                                )}
                                {h.discriminates_from.length > 0 && (
                                    <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                                        <span className="font-semibold">Competes with: </span>
                                        {h.discriminates_from.join(", ")}
                                    </p>
                                )}
                                {h.lineage_origins.length > 0 && (
                                    <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                                        <span className="font-semibold">Evidence lineage origins: </span>
                                        {h.lineage_origins.join(", ")}
                                    </p>
                                )}
                            </li>
                        )
                    })}
                </ul>
            )}
        </Panel>
    )
}
