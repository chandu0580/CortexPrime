"use client"

import { useState } from "react"
import Link from "next/link"

import { useInvestigations } from "@/hooks/queries/useInvestigator"
import {
    readAutonomy,
    readConclusion,
    readInvestigationStatus,
} from "@/lib/investigator/epistemic"
import EpistemicBadge from "./EpistemicBadge"
import TemporalStamp from "./TemporalStamp"
import { Empty, Loading, RequestFailure } from "./LoadState"

/**
 * The investigation list.
 *
 * It shows only fields the API actually returns. There is no severity, no
 * priority, no owner and no SLA column: none of those exist in the engine, and
 * a column filled with plausible-looking blanks is worse than a column that
 * isn't there.
 *
 * The list is not an incident aggregate. An incident may span several
 * investigations; inventing an aggregate to make the table look tidier would be
 * creating persistence for the frontend's convenience.
 */

const FILTERS = [
    { key: "all", label: "All" },
    { key: "active", label: "In progress" },
    { key: "completed", label: "Completed" },
] as const

export default function IncidentList() {
    const [state, setState] = useState<"all" | "active" | "completed">("all")
    const query = useInvestigations(state)

    return (
        <div className="space-y-4">
            <div role="group" aria-label="Filter investigations" className="flex flex-wrap gap-2">
                {FILTERS.map((filter) => (
                    <button
                        key={filter.key}
                        type="button"
                        aria-pressed={state === filter.key}
                        onClick={() => setState(filter.key)}
                        className="rounded-md border px-3 py-1.5 text-xs font-semibold"
                        style={{
                            borderColor: state === filter.key ? "var(--accent-border)" : "var(--border)",
                            background: state === filter.key ? "var(--accent-muted)" : "transparent",
                            color: state === filter.key ? "var(--accent-primary)" : "var(--text-secondary)",
                        }}
                    >
                        {filter.label}
                    </button>
                ))}
            </div>

            {query.isPending && <Loading label="investigations" />}
            {query.isError && <RequestFailure error={query.error} label="investigations" />}

            {query.data && query.data.items.length === 0 && (
                <Empty>
                    No investigations match this filter for your tenant. An empty list is not
                    a statement that nothing is wrong — it means nothing has been recorded
                    here.
                </Empty>
            )}

            {query.data && query.data.items.length > 0 && (
                <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-left text-sm">
                        <caption className="sr-only">
                            Investigations for the authenticated tenant
                        </caption>
                        <thead>
                            <tr style={{ color: "var(--text-muted)" }}>
                                <th scope="col" className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                    Investigation
                                </th>
                                <th scope="col" className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                    Subject
                                </th>
                                <th scope="col" className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                    Status
                                </th>
                                <th scope="col" className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                    Conclusion
                                </th>
                                <th scope="col" className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                    Autonomy
                                </th>
                                <th scope="col" className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide">
                                    Last ledger event
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {query.data.items.map((item) => (
                                <tr
                                    key={item.investigation_ref}
                                    className="border-t align-top"
                                    style={{ borderColor: "var(--border)" }}
                                >
                                    <td className="px-3 py-3">
                                        <Link
                                            href={`/investigator/${encodeURIComponent(item.investigation_ref)}`}
                                            className="font-mono text-xs underline underline-offset-2"
                                            style={{ color: "var(--accent-primary)" }}
                                        >
                                            {item.investigation_ref}
                                        </Link>
                                    </td>
                                    <td className="px-3 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                                        {item.subject_ref ?? "not recorded"}
                                    </td>
                                    <td className="px-3 py-3">
                                        <EpistemicBadge reading={readInvestigationStatus(item.status)} size="sm" />
                                    </td>
                                    <td className="px-3 py-3">
                                        {/* An in-progress investigation has no
                                            conclusion. That is shown as "in
                                            progress", never as a blank cell that
                                            reads like a missing value. */}
                                        <EpistemicBadge reading={readConclusion(item.conclusion_kind)} size="sm" />
                                    </td>
                                    <td className="px-3 py-3 text-xs" style={{ color: "var(--text-secondary)" }}>
                                        {readAutonomy(item.autonomy_level).label}
                                    </td>
                                    <td className="px-3 py-3">
                                        <TemporalStamp clock="recorded" value={item.last_event_at} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {query.data && (
                <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {query.data.note} Showing {query.data.count} of at most {query.data.limit}.
                </p>
            )}
        </div>
    )
}
