"use client"
import { motion, AnimatePresence } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { getAgentColor } from "@/lib/runtimeHelpers"
import { formatTimestamp } from "@/lib/formatting"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"

// ==========================================
// COGNITION STREAM  —  Live agent feed
// ==========================================

export default function CognitionStream() {
    const { events } = useCognitionStore()

    return (
        <GlassPanel>
            <SectionHeader
                title="Cognition Stream"
                subtitle="Live agent cognition"
                accent
            />

            <div className="cortex-scroll mt-3 max-h-72 space-y-1 overflow-y-auto">
                <AnimatePresence initial={false}>
                    {events.slice(0, 30).map((evt) => {
                        const color = getAgentColor(evt.agent)
                        return (
                            <motion.div
                                key={evt.event_id ?? `${evt.agent}-${evt.timestamp}`}
                                initial={{ opacity: 0, x: -10, height: 0 }}
                                animate={{ opacity: 1, x: 0, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ duration: 0.2 }}
                                className="flex items-start gap-2 overflow-hidden rounded-lg border border-[#e8f5ee] bg-[#f0f7f4] px-2.5 py-2"
                            >
                                {/* Agent dot with glow */}
                                <div
                                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                                    style={{ background: color, boxShadow: `0 0 5px ${color}` }}
                                />

                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-1.5">
                                        <span
                                            className="text-xs font-bold uppercase tracking-tight"
                                            style={{ color }}
                                        >
                                            {evt.agent}
                                        </span>
                                    <span className="text-xs text-[#a3a3a3]">·</span>
                                        <span className="text-xs text-[#737373]">{evt.event_type}</span>
                                    </div>
                                    <p className="line-clamp-2 text-sm leading-snug text-[#4a4a4a]">
                                        {evt.message}
                                    </p>
                                </div>

                                <span className="mt-0.5 shrink-0 text-xs tabular-nums text-[#737373]">
                                    {formatTimestamp(evt.timestamp)}
                                </span>
                            </motion.div>
                        )
                    })}
                </AnimatePresence>

                {events.length === 0 && (
                    <div className="flex flex-col items-center gap-2 py-8">
                        <div className="flex gap-1">
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    className="h-1 w-1 rounded-full bg-[#d1d1d1]"
                                    animate={{ opacity: [0.2, 1, 0.2] }}
                                    transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.3 }}
                                />
                            ))}
                        </div>
                        <p className="text-sm text-[#737373]">Waiting for cognition events…</p>
                    </div>
                )}
            </div>
        </GlassPanel>
    )
}
