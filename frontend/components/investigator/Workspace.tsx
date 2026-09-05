"use client"

import Link from "next/link"

import { useInvestigation } from "@/hooks/queries/useInvestigator"
import {
    readAutonomy,
    readConclusion,
    readInvestigationStatus,
} from "@/lib/investigator/epistemic"
import AssurancePanel from "./AssurancePanel"
import EpistemicBadge from "./EpistemicBadge"
import EvidenceExplorer from "./EvidenceExplorer"
import HistoricalExperience from "./HistoricalExperience"
import HypothesisPanel from "./HypothesisPanel"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import TimelinePanel from "./TimelinePanel"
import WorldStatePanel from "./WorldStatePanel"
import { Loading, RequestFailure } from "./LoadState"

/**
 * The investigation workspace.
 *
 * Read-only, and read-only by construction rather than by discipline: the only
 * data module it can reach is `product-api`, which exposes a single `productGet`
 * and no way to write anything. There is no execute button, no approve button
 * and no autonomy control on this screen, because there is no function they
 * could call.
 *
 * The default predicate for the World panel is the one Phase 9 actually
 * observes for Kubernetes workloads. It is a starting point a responder can
 * change, not an assertion that it is the interesting one.
 */

const DEFAULT_PREDICATE = "kubernetes.pod.restart_count"

export default function Workspace({ investigationRef }: { investigationRef: string }) {
    const query = useInvestigation(investigationRef)

    if (query.isPending) return <Loading label="investigation" />
    if (query.isError) return <RequestFailure error={query.error} label="this investigation" />
    if (!query.data) return null

    const investigation = query.data
    const status = readInvestigationStatus(investigation.status)
    const conclusion = readConclusion(investigation.conclusion_kind)
    const autonomy = readAutonomy(investigation.autonomy_level)

    return (
        <div className="space-y-5">
            <Link
                href="/investigator"
                className="inline-block text-xs underline underline-offset-2"
                style={{ color: "var(--accent-primary)" }}
            >
                ← All investigations
            </Link>

            <Panel title="Investigation" provenance="investigation">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                        <h1 className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>
                            {investigation.investigation_ref}
                        </h1>
                        <p className="mt-1 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                            {investigation.incident_ref ?? "no incident reference recorded"}
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <EpistemicBadge reading={status} size="sm" />
                        <EpistemicBadge reading={conclusion} size="sm" />
                    </div>
                </div>

                <p className="mt-3 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    {conclusion.meaning}
                </p>

                <div className="mt-4 flex flex-wrap gap-6">
                    <TemporalStamp clock="opened" value={investigation.opened_at} />
                    <TemporalStamp clock="recorded" value={investigation.last_event_at} />
                    <TemporalStamp clock="read" value={investigation.read_at} />
                </div>

                <div
                    className="mt-4 rounded-lg border p-3"
                    style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                >
                    <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                        Autonomy — {autonomy.label}
                    </p>
                    {/* Deliberately not a control. There is no toggle, no
                        dropdown and no request-promotion action: autonomy is
                        derived from platform policy and measured calibration,
                        and a product screen that offered to change it would be
                        offering something the platform does not support. */}
                    <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                        {autonomy.meaning}
                    </p>
                </div>

                {investigation.residual_uncertainty.length > 0 && (
                    <div
                        className="mt-4 rounded-lg border-l-2 py-2 pl-3"
                        style={{ borderColor: "var(--warning)" }}
                    >
                        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--warning)" }}>
                            Residual uncertainty
                        </p>
                        {investigation.residual_uncertainty.map((line) => (
                            <p key={line} className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                                {line}
                            </p>
                        ))}
                        <p className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                            Concluding is not knowing everything. What remains unresolved is
                            stated here rather than dropped once a conclusion is reached.
                        </p>
                    </div>
                )}

                <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 text-[11px] sm:grid-cols-4" style={{ color: "var(--text-secondary)" }}>
                    <dt>Hypotheses supported</dt>
                    <dd className="font-mono">{investigation.supported.length}</dd>
                    <dt>Ruled out</dt>
                    <dd className="font-mono">{investigation.eliminated.length}</dd>
                    <dt>Still open</dt>
                    <dd className="font-mono">{investigation.still_open.length}</dd>
                    <dt>Governed reads taken</dt>
                    <dd className="font-mono">{investigation.reads_taken}</dd>
                </dl>
            </Panel>

            <HypothesisPanel hypotheses={investigation.hypotheses} />

            <EvidenceExplorer evidence={investigation.evidence} />

            <TimelinePanel investigationRef={investigation.investigation_ref} />

            <AssurancePanel
                investigationRef={investigation.investigation_ref}
                assuranceVerified={investigation.assurance_verified}
            />

            {investigation.subject_ref && (
                <WorldStatePanel
                    subjectRef={investigation.subject_ref}
                    defaultPredicate={DEFAULT_PREDICATE}
                />
            )}

            <HistoricalExperience
                subjectRef={investigation.subject_ref}
                excludeRef={investigation.investigation_ref}
            />
        </div>
    )
}
