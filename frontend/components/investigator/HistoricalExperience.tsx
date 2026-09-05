"use client"

import Link from "next/link"

import { useInvestigations } from "@/hooks/queries/useInvestigator"
import { readConclusion } from "@/lib/investigator/epistemic"
import EpistemicBadge from "./EpistemicBadge"
import Panel from "./Panel"
import TemporalStamp from "./TemporalStamp"
import { Empty, Loading, RequestFailure } from "./LoadState"

/**
 * Past investigations of the same subject.
 *
 * This is the one panel most at risk of being read as current truth, so it is
 * the one that says loudest that it is not. It is headed HISTORICAL EXPERIENCE,
 * carries an explicit disclaimer, and shows every entry with the date it
 * concluded — a resolved investigation from three weeks ago tells you what was
 * true then and nothing about now.
 *
 * It introduces no retrieval system. It filters the already-exposed completed
 * investigation list by subject. There is no embedding, no vector search and no
 * similarity score: two investigations are related here because they name the
 * same subject, which is a fact, not a guess.
 */

export default function HistoricalExperience({
    subjectRef,
    excludeRef,
}: {
    subjectRef: string | null
    excludeRef: string
}) {
    const query = useInvestigations("completed")

    const related = (query.data?.items ?? []).filter(
        (item) =>
            item.investigation_ref !== excludeRef &&
            subjectRef !== null &&
            item.subject_ref === subjectRef,
    )

    return (
        <Panel title="Prior investigations of this subject" provenance="experience">
            <p
                className="mb-3 rounded border-l-2 pl-3 text-xs leading-relaxed"
                style={{ borderColor: "var(--warning)", color: "var(--text-secondary)" }}
            >
                These are <strong>past</strong> investigations. They may suggest what to look
                at and they <strong>do not establish what is true now</strong>. Nothing here
                is evidence about the current state of the system; for that, read the World
                state panel.
            </p>

            {query.isPending && <Loading label="prior investigations" />}
            {query.isError && <RequestFailure error={query.error} label="prior investigations" />}

            {query.data && related.length === 0 && (
                <Empty>
                    No completed investigation of this subject was found. That is not a
                    statement that none happened — only completed investigations are
                    listable.
                </Empty>
            )}

            {related.length > 0 && (
                <ul className="space-y-2">
                    {related.map((item) => (
                        <li
                            key={item.investigation_ref}
                            className="rounded-lg border p-3"
                            style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
                        >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <Link
                                    href={`/investigator/${encodeURIComponent(item.investigation_ref)}`}
                                    className="font-mono text-xs underline underline-offset-2"
                                    style={{ color: "var(--accent-primary)" }}
                                >
                                    {item.investigation_ref}
                                </Link>
                                <EpistemicBadge reading={readConclusion(item.conclusion_kind)} size="sm" />
                            </div>
                            <div className="mt-2">
                                <TemporalStamp clock="recorded" value={item.last_event_at} />
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    )
}
