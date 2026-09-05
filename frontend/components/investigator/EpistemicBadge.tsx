"use client"

import type { Reading } from "@/lib/investigator/epistemic"
import { TONE_STYLE } from "@/lib/investigator/epistemic"
import { cn } from "@/utils/cn"

/**
 * An epistemic state, shown as words.
 *
 * The label is always rendered as text, so the state survives greyscale, a
 * colour-blind reader and a screen reader — colour only emphasises what the
 * words already say (Part T). `meaning` is exposed both as a tooltip and, when
 * `explain` is set, as visible prose, because "CONFLICTED" only helps someone
 * who already knows it does not mean "false".
 *
 * This is deliberately not `components/ui/StatusPill`. That component's
 * vocabulary is success | warning | error | info, and STALE is not a warning
 * about a malfunction any more than CONFLICTED is an error.
 */
export default function EpistemicBadge({
    reading,
    explain = false,
    className,
    size = "md",
}: {
    reading: Reading
    explain?: boolean
    className?: string
    size?: "sm" | "md"
}) {
    const style = TONE_STYLE[reading.tone]
    return (
        <span className={cn("inline-flex flex-col gap-1", className)}>
            <span
                title={reading.meaning}
                data-tone={reading.tone}
                data-epistemic-label={reading.label}
                className={cn(
                    "inline-flex w-fit items-center rounded-md border font-semibold uppercase tracking-wide",
                    size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]",
                )}
                style={{
                    color: style.fg,
                    backgroundColor: style.bg,
                    borderColor: style.border,
                }}
            >
                {reading.label}
            </span>
            {explain && (
                <span className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    {reading.meaning}
                </span>
            )}
        </span>
    )
}
