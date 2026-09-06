"use client"

import { useState } from "react"
import Link from "next/link"

import {
    useApprovalQueue,
    useDecideApproval,
    type QueueFilters,
} from "@/hooks/queries/useInvestigator"
import { readAutonomy } from "@/lib/investigator/epistemic"
import { readStage } from "@/lib/investigator/remediation-vocabulary"
import type { ApprovalQueueItem } from "@/lib/investigator/types"
import EpistemicBadge from "./EpistemicBadge"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Empty, Loading, RequestFailure } from "./LoadState"

/**
 * The approval inbox — Phase 10.4.
 *
 * The product goal it serves: a responder should not have to know which
 * investigation raised a request in order to find it. Every pending decision in
 * the tenant appears here, ordered by the server.
 *
 * What this component does NOT do
 * -------------------------------
 * It computes nothing. Risk, blast radius, effect class, code trust, isolation
 * tier, reversibility, autonomy ceiling, assurance status, both digests and the
 * derived state are all read from the response. Ordering is the server's, not a
 * client-side sort — a queue two people sort differently is a queue they hand
 * over badly.
 *
 * There is deliberately **no bulk action**. No "approve all", no select-all
 * checkbox, no "run everything actionable". Each approval authorizes exactly
 * one action and is decided on its own screen, because that is the only way the
 * person deciding can have seen what they approved.
 */

const RISK_TONE: Record<string, string> = {
    critical: "var(--danger)",
    high: "var(--warning)",
    medium: "var(--accent-primary)",
    low: "var(--text-secondary)",
}

const FILTERS: Array<{ key: NonNullable<QueueFilters["status"]>; label: string }> = [
    { key: "actionable", label: "Needs attention" },
    { key: "decided", label: "Decided" },
    { key: "all", label: "All" },
]

function RiskTag({ risk }: { risk: string }) {
    return (
        <span
            className="inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
            style={{
                color: RISK_TONE[risk] ?? "var(--text-secondary)",
                borderColor: RISK_TONE[risk] ?? "var(--border-strong)",
            }}
            // The word is the meaning; the colour only emphasises it.
            title={`Risk ${risk}, derived by the platform from the declared effect. An undeclared effect is CRITICAL, never low.`}
        >
            {risk}
        </span>
    )
}

function QueueRow({
    item, onReview,
}: {
    item: ApprovalQueueItem
    onReview: (id: string) => void
}) {
    const stage = readStage(item.state)
    return (
        <tr className="border-t align-top" style={{ borderColor: "var(--border)" }}>
            <td className="px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                    <EpistemicBadge reading={stage} size="sm" />
                    <RiskTag risk={item.risk} />
                </div>
            </td>
            <td className="px-3 py-3">
                <p className="text-sm" style={{ color: "var(--text-primary)" }}>
                    Restart <strong>{item.workload || "unknown workload"}</strong>
                </p>
                <p className="font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                    {item.namespace}
                </p>
                <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {item.blast_radius}
                </p>
            </td>
            <td className="px-3 py-3">
                {item.investigation_ref ? (
                    <Link
                        href={`/investigator/${encodeURIComponent(item.investigation_ref)}`}
                        className="font-mono text-[11px] underline underline-offset-2"
                        style={{ color: "var(--accent-primary)" }}
                    >
                        {item.investigation_ref}
                    </Link>
                ) : (
                    <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                        no investigation recorded
                    </span>
                )}
                <p className="mt-1 font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                    {item.incident_ref ?? ""}
                </p>
            </td>
            <td className="px-3 py-3">
                <p className="font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                    {item.requested_by}
                </p>
                <div className="mt-1 space-y-1">
                    <TemporalStamp clock="recorded" value={item.requested_at} />
                </div>
            </td>
            <td className="px-3 py-3">
                <TemporalStamp clock="recorded" value={item.expires_at} />
                {item.expired && (
                    <p className="mt-1 text-[11px]" style={{ color: "var(--warning)" }}>
                        past expiry — no longer decidable
                    </p>
                )}
            </td>
            <td className="px-3 py-3">
                <p className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
                    {item.assurance_status === "verified"
                        ? "Assurance has ruled"
                        : "Assurance has not ruled"}
                </p>
                <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {item.evidence_count} evidence refs
                </p>
            </td>
            <td className="px-3 py-3">
                {/* "Review", never "Run". Nothing executes from a list row: the
                    only way to a decision is a screen showing the whole action.
                    A viewer without authority still gets Review -- hiding the row
                    would leave them unable to see what is waiting, or to tell a
                    tenant boundary from a permission one. */}
                <button
                    type="button"
                    onClick={() => onReview(item.approval_id)}
                    className="rounded border px-3 py-1.5 text-xs font-semibold"
                    style={{ borderColor: "var(--accent-border)", color: "var(--accent-primary)" }}
                >
                    Review
                </button>
                {item.actionable && !item.can_approve && (
                    <p className="mt-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                        you cannot approve
                    </p>
                )}
            </td>
        </tr>
    )
}

function Fact({ label, value, mono = false, hint }: {
    label: string
    value: React.ReactNode
    mono?: boolean
    hint?: string
}) {
    return (
        <div className="min-w-0">
            <dt className="text-[10px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                {label}
            </dt>
            <dd
                className={mono ? "break-all font-mono text-xs" : "text-xs"}
                style={{ color: "var(--text-primary)" }}
                title={hint}
            >
                {value}
            </dd>
        </div>
    )
}

/**
 * The decision screen.
 *
 * Shows the same authoritative preview the workspace shows, because it is the
 * same projection from the same endpoint. The action cannot be edited: there is
 * no input that changes what runs, and a responder who wants something else
 * rejects this and a new proposal is raised.
 */
function ApprovalDetail({
    item, onClose,
}: {
    item: ApprovalQueueItem
    onClose: () => void
}) {
    const [confirm, setConfirm] = useState("")
    const [why, setWhy] = useState("")
    const decide = useDecideApproval(item.investigation_ref ?? "")
    const confirmed = confirm.trim() === item.workload
    const stage = readStage(item.state)
    // The SERVER decided this. The component renders it and never computes it:
    // whether this person may approve is a governance question, and a frontend
    // that answered it would be a second authority however carefully written.
    const mayDecide = item.can_approve

    return (
        <Panel
            title={`Approval ${item.approval_id}`}
            provenance="investigation"
            actions={
                <button
                    type="button"
                    onClick={onClose}
                    className="text-xs underline underline-offset-2"
                    style={{ color: "var(--accent-primary)" }}
                >
                    Back to the queue
                </button>
            }
        >
            <div className="flex flex-wrap items-center gap-2">
                <EpistemicBadge reading={stage} size="sm" />
                <RiskTag risk={item.risk} />
            </div>
            <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {stage.meaning}
            </p>

            <p className="mt-4 text-sm" style={{ color: "var(--text-primary)" }}>
                <strong>What will happen:</strong> restart <strong>{item.workload}</strong> in
                namespace <strong>{item.namespace}</strong>.
            </p>

            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <Fact label="Capability" value={`${item.capability_ref} v${item.capability_version}`} mono />
                <Fact label="Provider" value={item.provider ?? "not recorded"} mono />
                <Fact label="Environment" value={item.environment} />
                <Fact label="Parameters" value={JSON.stringify(item.parameters)} mono />
                <Fact label="Effect" value={(item.side_effect_class ?? "undeclared").replace(/_/g, " ").toUpperCase()} />
                <Fact label="Effect semantics" value={item.effect_semantics ?? "not declared"} />
                <Fact label="Code trust" value={(item.code_trust ?? "unknown").toUpperCase()} />
                <Fact label="Isolation" value={(item.isolation_tier ?? "unknown").toUpperCase()} />
                <Fact
                    label="Reversibility"
                    value={item.reversible
                        ? "REVERSIBLE — an inverse action is declared"
                        : "IRREVERSIBLE — there is no inverse action"}
                />
                <Fact label="Blast radius" value={item.blast_radius} />
                <Fact label="Autonomy ceiling" value={readAutonomy(item.autonomy_ceiling).label}
                      hint={item.autonomy_note} />
                <Fact label="Requested by" value={item.requested_by} mono />
                <Fact label="Capability digest" value={item.capability_digest} mono />
                <Fact label="Approval digest" value={item.approval_digest} mono
                      hint="Binds this approval to THIS action. A different namespace or workload is a different digest." />
                <Fact label="Action digest" value={item.action_digest ?? "not yet in existence"}
                      hint={item.action_digest_note} />
                <Fact label="Assurance" value={item.assurance_status.replace(/_/g, " ")}
                      hint={item.assurance_note} />
            </dl>

            <p className="mt-3 text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {item.action_digest_note}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {item.autonomy_note}
            </p>

            <div className="mt-4 flex flex-wrap gap-6">
                <TemporalStamp clock="recorded" value={item.requested_at} />
                <TemporalStamp clock="recorded" value={item.expires_at} />
            </div>

            {item.justification && (
                <p className="mt-3 text-xs" style={{ color: "var(--text-secondary)" }}>
                    <span className="font-semibold">Stated reason: </span>
                    {item.justification}
                </p>
            )}

            {!item.actionable ? (
                <p
                    className="mt-4 rounded border px-3 py-2 text-xs leading-relaxed"
                    style={{ borderColor: "var(--border-strong)", color: "var(--text-secondary)" }}
                >
                    This approval can no longer be decided. It is shown for the record.
                </p>
            ) : !mayDecide ? (
                /* Two different sentences, deliberately. "Nobody may decide
                   this" and "you may not decide this" are different facts, and
                   a responder who cannot tell them apart cannot tell whether to
                   find a colleague or let it expire. */
                <div
                    className="mt-4 rounded border px-3 py-2"
                    style={{ borderColor: "var(--border-strong)" }}
                    role="note"
                >
                    <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                        You do not have approval authority in this tenant
                    </p>
                    <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                        This approval is still open and someone with approver authority
                        can decide it. Tenant membership alone does not confer that
                        authority, and it is not something this page can grant.
                    </p>
                    <p className="mt-1 font-mono text-[11px]" style={{ color: "var(--text-muted)" }}>
                        {item.authority_reason}
                    </p>
                </div>
            ) : (
                <form
                    className="mt-4 space-y-2 border-t pt-3"
                    style={{ borderColor: "var(--border)" }}
                    onSubmit={(event) => {
                        event.preventDefault()
                        if (!confirmed) return
                        decide.mutate({
                            approvalId: item.approval_id,
                            decision: "approve",
                            justification: why || undefined,
                            confirmWorkload: confirm.trim(),
                        })
                    }}
                >
                    <label htmlFor="queue-why" className="block text-[11px]"
                           style={{ color: "var(--text-secondary)" }}>
                        Why? (recorded in the audit trail)
                    </label>
                    <input
                        id="queue-why"
                        value={why}
                        onChange={(event) => setWhy(event.target.value)}
                        className="w-full rounded border px-2 py-1 text-xs"
                        style={{ borderColor: "var(--border-strong)", background: "var(--surface-raised)",
                                 color: "var(--text-primary)" }}
                    />
                    <label htmlFor="queue-confirm" className="block text-[11px]"
                           style={{ color: "var(--text-secondary)" }}>
                        Type <strong>{item.workload}</strong> to confirm you have read the action
                    </label>
                    <input
                        id="queue-confirm"
                        value={confirm}
                        onChange={(event) => setConfirm(event.target.value)}
                        aria-describedby="queue-confirm-help"
                        className="w-full rounded border px-2 py-1 font-mono text-xs"
                        style={{ borderColor: "var(--border-strong)", background: "var(--surface-raised)",
                                 color: "var(--text-primary)" }}
                    />
                    <p id="queue-confirm-help" className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                        This authorizes this one action. There is no approve-all and no
                        tenant-wide approval. To do something different, reject this and raise
                        a new proposal — the approved action is never edited.
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                        <button
                            type="submit"
                            disabled={!confirmed || decide.isPending}
                            className="rounded border px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
                            style={{ borderColor: "var(--success-border)", color: "var(--success)" }}
                        >
                            {decide.isPending ? "Recording…" : "Approve this action"}
                        </button>
                        <button
                            type="button"
                            disabled={decide.isPending}
                            onClick={() =>
                                decide.mutate({
                                    approvalId: item.approval_id,
                                    decision: "reject",
                                    justification: why || undefined,
                                })
                            }
                            className="rounded border px-3 py-1.5 text-xs font-semibold"
                            style={{ borderColor: "var(--border-strong)", color: "var(--text-secondary)" }}
                        >
                            Reject
                        </button>
                    </div>
                    {decide.isError && <RequestFailure error={decide.error} label="the decision" />}
                    {decide.isSuccess && (
                        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                            Recorded. Reopen the queue to see the current state.
                        </p>
                    )}
                </form>
            )}
        </Panel>
    )
}

export default function ApprovalQueue() {
    const [status, setStatus] = useState<NonNullable<QueueFilters["status"]>>("actionable")
    const [risk, setRisk] = useState<QueueFilters["risk"] | undefined>(undefined)
    const [selected, setSelected] = useState<string | null>(null)
    const query = useApprovalQueue({ status, risk })

    const item = query.data?.items.find((i) => i.approval_id === selected) ?? null
    if (item) {
        return <ApprovalDetail item={item} onClose={() => setSelected(null)} />
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter approvals">
                {FILTERS.map((filter) => (
                    <button
                        key={filter.key}
                        type="button"
                        aria-pressed={status === filter.key}
                        onClick={() => setStatus(filter.key)}
                        className="rounded-md border px-3 py-1.5 text-xs font-semibold"
                        style={{
                            borderColor: status === filter.key ? "var(--accent-border)" : "var(--border)",
                            background: status === filter.key ? "var(--accent-muted)" : "transparent",
                            color: status === filter.key ? "var(--accent-primary)" : "var(--text-secondary)",
                        }}
                    >
                        {filter.label}
                    </button>
                ))}
                <label htmlFor="risk-filter" className="sr-only">
                    Filter by risk
                </label>
                <select
                    id="risk-filter"
                    value={risk ?? ""}
                    onChange={(event) =>
                        setRisk((event.target.value || undefined) as QueueFilters["risk"])}
                    className="rounded-md border px-2 py-1.5 text-xs"
                    style={{ borderColor: "var(--border)", background: "transparent",
                             color: "var(--text-secondary)" }}
                >
                    <option value="">Any risk</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>
            </div>

            {query.data && !query.data.viewer_can_approve && (
                <div
                    className="rounded border px-3 py-2"
                    style={{ borderColor: "var(--border-strong)", background: "var(--surface-raised)" }}
                    role="note"
                >
                    <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                        You do not have approval authority in this tenant
                    </p>
                    <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                        You can see what is waiting, and you cannot decide any of it.
                        Approver authority is granted per tenant by an administrator; it
                        is not implied by membership and there is no control here that
                        could grant it.
                    </p>
                </div>
            )}

            {query.isPending && <Loading label="the approval queue" />}
            {query.isError && <RequestFailure error={query.error} label="the approval queue" />}

            {query.data && query.data.items.length === 0 && (
                <Empty>
                    Nothing matches this filter. An empty queue is not a statement that
                    nothing needs attention — it means nothing has been recorded here.
                </Empty>
            )}

            {query.data && query.data.items.length > 0 && (
                <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-left text-sm">
                        <caption className="sr-only">
                            Approvals awaiting a decision, across every investigation in this tenant
                        </caption>
                        <thead>
                            <tr style={{ color: "var(--text-muted)" }}>
                                {["State", "Remediation", "Investigation", "Requested",
                                  "Expires", "Assurance", ""].map((heading) => (
                                    <th key={heading} scope="col"
                                        className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                        {heading}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {query.data.items.map((row) => (
                                <QueueRow key={row.approval_id} item={row} onReview={setSelected} />
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {query.data && (
                <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                    {query.data.note} Showing {query.data.count} of at most {query.data.limit};{" "}
                    {query.data.actionable_count} can still be decided. Ordered by the server:{" "}
                    {query.data.ordering}.
                </p>
            )}
        </div>
    )
}
