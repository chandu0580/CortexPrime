"use client"

import { useTimeline } from "@/hooks/queries/useInvestigator"
import { readAutonomy } from "@/lib/investigator/epistemic"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Empty, Loading, RequestFailure } from "./LoadState"

/**
 * What was recorded, in the order it was recorded.
 *
 * Only events the ledger actually holds are drawn. There is no interpolation
 * between them, no synthetic "investigation started analysing" entry, and no
 * duration bar implying something continuous happened in a gap. A timeline that
 * fills its own gaps is a story, not a record.
 *
 * Every time here is a LEDGER time — when CortexPrime committed the event — and
 * it is labelled as such rather than presented as when the world changed.
 */

export default function TimelinePanel({ investigationRef }: { investigationRef: string }) {
    const query = useTimeline(investigationRef)

    return (
        <Panel
            title="Investigation timeline"
            provenance="ledger"
            actions={
                query.data ? (
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {query.data.count} recorded events
                    </span>
                ) : null
            }
        >
            {query.isPending && <Loading label="timeline" />}
            {query.isError && <RequestFailure error={query.error} label="the timeline" />}

            {query.data && query.data.events.length === 0 && (
                <Empty>No events have been recorded for this investigation.</Empty>
            )}

            {query.data && query.data.events.length > 0 && (
                <>
                    <ol className="space-y-3">
                        {query.data.events.map((event) => (
                            <li
                                key={event.seq}
                                className="relative border-l pl-4"
                                style={{ borderColor: "var(--border-strong)" }}
                            >
                                <span
                                    className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full"
                                    style={{ background: "var(--accent-primary)" }}
                                    aria-hidden="true"
                                />
                                <div className="flex flex-wrap items-baseline gap-2">
                                    <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-primary)" }}>
                                        {event.event_kind.replace(/_/g, " ")}
                                    </span>
                                    <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                        {event.from_status ? `${event.from_status} → ` : ""}
                                        {event.to_status}
                                    </span>
                                    <span className="font-mono text-[10px]" style={{ color: "var(--text-muted)" }}>
                                        #{event.seq}
                                    </span>
                                </div>
                                {event.detail && (
                                    <p className="mt-1 font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                        {event.detail}
                                    </p>
                                )}
                                <div className="mt-1 flex flex-wrap items-end gap-4">
                                    <TemporalStamp clock="recorded" value={event.recorded_at} />
                                    {event.autonomy_level && (
                                        <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                                            autonomy at this event: {readAutonomy(event.autonomy_level).label}
                                        </span>
                                    )}
                                </div>
                            </li>
                        ))}
                    </ol>
                    <p className="mt-3 text-[11px]" style={{ color: "var(--text-muted)" }}>
                        {query.data.note}
                    </p>
                </>
            )}
        </Panel>
    )
}
