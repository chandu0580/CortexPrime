"use client"

import { cn } from "@/utils/cn"

/**
 * A titled section, using the existing theme tokens rather than new colours.
 *
 * `provenance` names where the content came from — CURRENT WORLD, HISTORICAL
 * EXPERIENCE, ASSURANCE, LEDGER. Part K turns on that distinction being
 * unmissable: past investigations may inform an investigation and may never
 * establish current truth, so the panel that carries them says so in its own
 * header rather than relying on the reader's memory of which column they are in.
 */

export type Provenance = "world" | "investigation" | "assurance" | "ledger" | "experience"

const PROVENANCE: Record<Provenance, { tag: string; note: string; accent: string }> = {
    world: {
        tag: "CURRENT WORLD",
        note: "Authoritative state derived from observations, with freshness and authority.",
        accent: "var(--accent-primary)",
    },
    investigation: {
        tag: "INVESTIGATION",
        note: "The reasoning state of this investigation. Not world truth.",
        accent: "var(--info)",
    },
    assurance: {
        tag: "ASSURANCE",
        note: "Independent verification, recorded by the verifier.",
        accent: "var(--success)",
    },
    ledger: {
        tag: "RECORDED LEDGER",
        note: "Events exactly as committed. Nothing between them is inferred.",
        accent: "var(--text-secondary)",
    },
    experience: {
        tag: "HISTORICAL EXPERIENCE",
        note: "Past investigations. These do NOT establish current truth and are not evidence about the world now.",
        accent: "var(--warning)",
    },
}

export default function Panel({
    title,
    provenance,
    children,
    actions,
    className,
}: {
    title: string
    provenance: Provenance
    children: React.ReactNode
    actions?: React.ReactNode
    className?: string
}) {
    const meta = PROVENANCE[provenance]
    return (
        <section
            aria-label={`${title} — ${meta.tag}`}
            className={cn("rounded-xl border", className)}
            style={{
                borderColor: "var(--border)",
                background: "var(--surface)",
            }}
        >
            <header
                className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-3"
                style={{ borderColor: "var(--border)" }}
            >
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                            {title}
                        </h2>
                        <span
                            className="rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                            style={{
                                color: meta.accent,
                                borderColor: meta.accent,
                                background: "transparent",
                            }}
                        >
                            {meta.tag}
                        </span>
                    </div>
                    <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                        {meta.note}
                    </p>
                </div>
                {actions}
            </header>
            <div className="px-4 py-3">{children}</div>
        </section>
    )
}
