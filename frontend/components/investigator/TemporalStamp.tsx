"use client"

/**
 * A timestamp that says which clock it came from.
 *
 * The workspace shows at least three different times and they mean different
 * things:
 *
 *   observed_at   — when the WORLD was in this state, per the instrument
 *   retrieved_at  — when CORTEXPRIME fetched it
 *   recorded_at   — when CortexPrime committed a ledger event
 *
 * A metric scraped at 10:04 may describe the world at 10:00. Rendering either
 * of those under a bare heading of "Time" asserts an event time nobody
 * measured, so this component refuses to display a value without its label.
 */

export type Clock = "observed" | "retrieved" | "recorded" | "read" | "opened" | "asked"

const CLOCKS: Record<Clock, { label: string; hint: string }> = {
    observed: {
        label: "World observed at",
        hint: "When the instrument says the world was in this state.",
    },
    retrieved: {
        label: "CortexPrime learned at",
        hint: "When CortexPrime fetched this. Not the time the world changed.",
    },
    recorded: {
        label: "Recorded in ledger at",
        hint: "When CortexPrime committed this event. A ledger time, not a world time.",
    },
    read: {
        label: "This answer computed at",
        hint: "When the server computed this response. Shown so a cached view cannot pass for a live one.",
    },
    opened: {
        label: "Investigation opened at",
        hint: "When the investigation was created.",
    },
    asked: {
        label: "World asked about",
        hint: "The instant the world was queried about.",
    },
}

function format(iso: string | null | undefined): string {
    if (!iso) return "not recorded"
    const parsed = new Date(iso)
    if (Number.isNaN(parsed.getTime())) return iso
    // Explicit UTC. A local rendering of an incident time is how two people on
    // a call end up describing different moments with the same number.
    return `${parsed.toISOString().replace("T", " ").replace(/\.\d+Z$/, "")} UTC`
}

export default function TemporalStamp({
    clock,
    value,
    className,
}: {
    clock: Clock
    value: string | null | undefined
    className?: string
}) {
    const meta = CLOCKS[clock]
    return (
        <span className={className} title={meta.hint}>
            <span
                className="block text-[10px] uppercase tracking-wide"
                style={{ color: "var(--text-muted)" }}
            >
                {meta.label}
            </span>
            <span
                className="block font-mono text-xs"
                style={{ color: value ? "var(--text-primary)" : "var(--text-muted)" }}
            >
                {format(value)}
            </span>
        </span>
    )
}

export { format as formatInstant }
