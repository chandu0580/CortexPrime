"use client"

import { useState } from "react"

import {
    useApprovals,
    useDecideApproval,
    useExecuteApproval,
    useRemediation,
    useRequestApproval,
} from "@/hooks/queries/useInvestigator"
import { readAutonomy } from "@/lib/investigator/epistemic"
import { readApproval, readStage } from "@/lib/investigator/remediation-vocabulary"
import type { Approval, RemediationProposal } from "@/lib/investigator/types"
import EpistemicBadge from "./EpistemicBadge"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Empty, Loading, RequestFailure } from "./LoadState"

/**
 * The governed remediation, its immutable preview, and the human decision.
 *
 * What this component does NOT do
 * -------------------------------
 * It computes no value shown in the preview. The capability, provider, target,
 * parameters, side-effect class, code trust, isolation tier, reversibility,
 * blast radius, autonomy ceiling and both digests are **read from the response**
 * and rendered. If the server does not say it, this screen does not show it.
 *
 * It also holds no authority. Requesting, deciding and executing are three
 * POSTs whose bodies carry a justification, a decision word and a confirmation
 * string. The tenant, the action and the approver's identity are all resolved
 * server-side from the verified session, so there is nothing here for a
 * tampered client to change.
 *
 * There is no autonomy control. Autonomy is displayed as a platform-set ceiling
 * and there is no route that could raise it.
 */

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

function ActionPreview({ proposal }: { proposal: RemediationProposal }) {
    return (
        <div
            className="rounded-lg border p-3"
            style={{ borderColor: "var(--border-strong)", background: "var(--surface-raised)" }}
        >
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide"
               style={{ color: "var(--text-primary)" }}>
                What will happen
            </p>
            <p className="mb-3 text-sm" style={{ color: "var(--text-primary)" }}>
                Restart <strong>{proposal.workload}</strong> in namespace{" "}
                <strong>{proposal.namespace}</strong>.
            </p>

            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <Fact label="Capability" value={`${proposal.capability_ref} v${proposal.capability_version}`} mono />
                <Fact label="Provider" value={proposal.provider} mono />
                <Fact label="Tenant" value={proposal.tenant_id} mono
                      hint="Resolved from your authenticated session. Not something this page can set." />
                <Fact label="Environment" value={proposal.environment} />
                <Fact label="Parameters" value={JSON.stringify(proposal.parameters)} mono />
                <Fact label="Side effect" value={proposal.side_effect_class.replace(/_/g, " ").toUpperCase()} />
                <Fact label="Effect semantics" value={proposal.effect_semantics ?? "not declared"} />
                <Fact label="Code trust" value={proposal.code_trust.toUpperCase()} />
                <Fact label="Isolation tier" value={proposal.isolation_tier.toUpperCase()} />
                <Fact
                    label="Reversibility"
                    value={
                        proposal.reversible
                            ? "REVERSIBLE — an inverse action is declared"
                            : "IRREVERSIBLE — there is no inverse action"
                    }
                />
                <Fact label="Blast radius" value={proposal.blast_radius} />
                <Fact label="Autonomy ceiling" value={readAutonomy(proposal.autonomy_ceiling).label}
                      hint="Platform-set. This screen cannot change it." />
                <Fact label="Approval required" value={proposal.approval_required ? "YES — a human must decide" : "no"} />
                <Fact label="Capability digest" value={proposal.capability_digest} mono />
                <Fact
                    label="Action (approval) digest"
                    value={proposal.approval_digest}
                    mono
                    hint="Binds an approval to THIS action. A different namespace or workload produces a different digest, and an approval for one cannot authorize the other."
                />
            </dl>

            {proposal.evidence_refs.length > 0 && (
                <div className="mt-3">
                    <span className="text-[10px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                        Evidence this rests on ({proposal.evidence_refs.length})
                    </span>
                    <ul className="mt-1 space-y-0.5">
                        {proposal.evidence_refs.map((ref) => (
                            <li key={ref} className="font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                {ref}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <p className="mt-3 text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                Every value above is read from the governed capability contract and the
                platform&rsquo;s own digest function. This page computes none of them, and
                cannot change any of them.
            </p>
        </div>
    )
}

function ApprovalCard({
    approval, proposal, investigationRef,
}: {
    approval: Approval
    proposal: RemediationProposal
    investigationRef: string
}) {
    const [confirm, setConfirm] = useState("")
    const [why, setWhy] = useState("")
    const decide = useDecideApproval(investigationRef)
    const execute = useExecuteApproval(investigationRef)
    const reading = readApproval(approval.state, approval.expired)

    // Explicit confirmation. The operator types the workload name, which the
    // SERVER checks against what it stored — so this cannot be satisfied by a
    // stray click, and cannot change what runs.
    const confirmed = confirm.trim() === approval.workload
    const pending = approval.state === "pending" && !approval.expired

    return (
        <li
            className="rounded-lg border p-3"
            style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
        >
            <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                    {approval.approval_id}
                </p>
                <EpistemicBadge reading={reading} size="sm" />
            </div>
            <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {reading.meaning}
            </p>

            <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
                <Fact label="Target" value={`${approval.namespace}/${approval.workload}`} mono />
                <Fact label="Requested by" value={approval.requested_by} mono />
                <Fact label="Decided by" value={approval.decided_by ?? "not yet decided"} mono />
                <Fact label="Action digest" value={approval.approval_digest} mono />
            </dl>

            <div className="mt-3 flex flex-wrap gap-6">
                <TemporalStamp clock="recorded" value={approval.requested_at} />
                <TemporalStamp clock="recorded" value={approval.expires_at} />
            </div>
            <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                Approvals expire. There is no option to grant one that does not.
            </p>

            {approval.justification && (
                <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                    <span className="font-semibold">Stated reason: </span>
                    {approval.justification}
                </p>
            )}

            {pending && (
                <form
                    className="mt-4 space-y-2 border-t pt-3"
                    style={{ borderColor: "var(--border)" }}
                    onSubmit={(event) => {
                        event.preventDefault()
                        if (!confirmed) return
                        decide.mutate({
                            approvalId: approval.approval_id,
                            decision: "approve",
                            justification: why || undefined,
                            confirmWorkload: confirm.trim(),
                        })
                    }}
                >
                    <label htmlFor={`why-${approval.approval_id}`} className="block text-[11px]"
                           style={{ color: "var(--text-secondary)" }}>
                        Why are you approving this? (recorded in the audit trail)
                    </label>
                    <input
                        id={`why-${approval.approval_id}`}
                        value={why}
                        onChange={(event) => setWhy(event.target.value)}
                        className="w-full rounded border px-2 py-1 text-xs"
                        style={{ borderColor: "var(--border-strong)", background: "var(--surface)",
                                 color: "var(--text-primary)" }}
                    />

                    <label htmlFor={`confirm-${approval.approval_id}`} className="block text-[11px]"
                           style={{ color: "var(--text-secondary)" }}>
                        Type <strong>{approval.workload}</strong> to confirm you have read the
                        action above
                    </label>
                    <input
                        id={`confirm-${approval.approval_id}`}
                        value={confirm}
                        onChange={(event) => setConfirm(event.target.value)}
                        aria-describedby={`confirm-help-${approval.approval_id}`}
                        className="w-full rounded border px-2 py-1 font-mono text-xs"
                        style={{ borderColor: "var(--border-strong)", background: "var(--surface)",
                                 color: "var(--text-primary)" }}
                    />
                    <p id={`confirm-help-${approval.approval_id}`} className="text-[11px]"
                       style={{ color: "var(--text-muted)" }}>
                        This approval authorizes this one action only. There is no approve-all
                        and no tenant-wide approval.
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
                                    approvalId: approval.approval_id,
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
                </form>
            )}

            {approval.state === "granted" && !approval.expired
                && !approval.consumed_by_execution && approval.can_execute === false && (
                /* Phase 10.7: an approval existing is no longer sufficient to
                   offer Execute. Executing is a third act with its own scoped
                   grant, and the server says whether this caller holds it. */
                <p
                    className="mt-4 rounded border px-3 py-2 text-xs leading-relaxed"
                    style={{ borderColor: "var(--border-strong)", color: "var(--text-secondary)" }}
                    role="note"
                >
                    This action is approved and you are not authorized to execute it.
                    Approving and executing are different acts with different grants.
                </p>
            )}

            {approval.state === "granted" && !approval.expired
                && !approval.consumed_by_execution && approval.can_execute !== false && (
                <div className="mt-4 border-t pt-3" style={{ borderColor: "var(--border)" }}>
                    <button
                        type="button"
                        disabled={execute.isPending}
                        onClick={() => execute.mutate(approval.approval_id)}
                        className="rounded border px-3 py-1.5 text-xs font-semibold"
                        style={{ borderColor: "var(--accent-border)", color: "var(--accent-primary)" }}
                    >
                        {execute.isPending ? "Dispatching…" : "Run the approved action"}
                    </button>
                    <p className="mt-2 text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                        This hands the approved action to the governed chain. Authorization,
                        the approval check and the isolated worker all run again — this button
                        does not bypass any of them, and a refusal from any of them stops it.
                    </p>
                    {execute.isError && <RequestFailure error={execute.error} label="the execution" />}
                </div>
            )}

            {execute.data && (
                <div className="mt-3 rounded border p-3"
                     style={{ borderColor: "var(--border-strong)" }}>
                    <div className="flex flex-wrap items-center gap-2">
                        <EpistemicBadge reading={readStage("executing")} size="sm" />
                    </div>
                    <p className="mt-2 font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                        {execute.data.execution_ref}
                    </p>
                    {/* Deliberately not a success message. What happened in the
                        world is a separate question, answered by a separate read. */}
                    <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                        {execute.data.note ??
                            "Accepted by the governed chain. Whether the world changed is " +
                            "established by an independent World observation, not by this response."}
                    </p>
                </div>
            )}

            {approval.consumed_by_execution && (
                <p className="mt-3 font-mono text-[11px]" style={{ color: "var(--text-muted)" }}>
                    used by execution {approval.consumed_by_execution}
                </p>
            )}
        </li>
    )
}

export default function RemediationPanel({ investigationRef }: { investigationRef: string }) {
    const [justification, setJustification] = useState("")
    const proposal = useRemediation(investigationRef)
    const approvals = useApprovals(investigationRef)
    const request = useRequestApproval(investigationRef)

    return (
        <Panel title="Governed remediation" provenance="investigation">
            {proposal.isPending && <Loading label="the remediation proposal" />}
            {proposal.isError && (
                <>
                    <RequestFailure error={proposal.error} label="the remediation proposal" />
                    <p className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                        CortexPrime proposes a remediation only where a governed capability
                        has actually been commissioned for the subject. Nothing is offered
                        that the platform would refuse.
                    </p>
                </>
            )}

            {proposal.data && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                        <EpistemicBadge reading={readStage("proposed")} size="sm" />
                        <span className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                            {proposal.data.operation}
                        </span>
                    </div>

                    <ActionPreview proposal={proposal.data} />

                    <form
                        className="space-y-2"
                        onSubmit={(event) => {
                            event.preventDefault()
                            request.mutate(justification)
                        }}
                    >
                        <label htmlFor="request-why" className="block text-[11px]"
                               style={{ color: "var(--text-secondary)" }}>
                            Why is this remediation being requested?
                        </label>
                        <input
                            id="request-why"
                            value={justification}
                            onChange={(event) => setJustification(event.target.value)}
                            className="w-full rounded border px-2 py-1 text-xs"
                            style={{ borderColor: "var(--border-strong)", background: "var(--surface-raised)",
                                     color: "var(--text-primary)" }}
                        />
                        <button
                            type="submit"
                            disabled={request.isPending}
                            className="rounded border px-3 py-1.5 text-xs font-semibold"
                            style={{ borderColor: "var(--accent-border)", color: "var(--accent-primary)" }}
                        >
                            {request.isPending ? "Requesting…" : "Request human approval"}
                        </button>
                        {request.isError && <RequestFailure error={request.error} label="the approval request" />}
                    </form>
                </div>
            )}

            <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold uppercase tracking-wide"
                    style={{ color: "var(--text-primary)" }}>
                    Approvals for this investigation
                </h3>
                {approvals.isPending && <Loading label="approvals" />}
                {approvals.isError && <RequestFailure error={approvals.error} label="approvals" />}
                {approvals.data && approvals.data.items.length === 0 && (
                    <Empty>
                        No approval has been requested. Nothing can run until a named human
                        approves this exact action.
                    </Empty>
                )}
                {approvals.data && approvals.data.items.length > 0 && proposal.data && (
                    <ul className="mt-3 space-y-3">
                        {approvals.data.items.map((approval) => (
                            <ApprovalCard
                                key={approval.approval_id}
                                approval={approval}
                                proposal={proposal.data}
                                investigationRef={investigationRef}
                            />
                        ))}
                    </ul>
                )}
            </div>
        </Panel>
    )
}
