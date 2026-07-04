"use client"
import { motion } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import { formatTimestamp } from "@/lib/formatting"

// ==========================================
// COMPUTER USE STREAM
// ==========================================

export default function ComputerUseStream() {
    const { events } = useCognitionStore()

    const computerEvents = events.filter((e) =>
        e.event_type?.toLowerCase().includes("computer") ||
        e.agent?.toLowerCase().includes("computer") ||
        e.event_type?.toLowerCase().includes("browser") ||
        e.event_type?.toLowerCase().includes("desktop")
    )

    return (
        <GlassPanel>
            <SectionHeader title="Computer Use Stream" subtitle="Autonomous computer interaction log" />
            <div className="cortex-scroll space-y-1.5 max-h-80 overflow-y-auto">
                {computerEvents.slice(0, 20).map((evt, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex gap-2 rounded-md border border-[#4a8c70]/10 bg-[#4a8c70]/5 px-3 py-2 text-xs"
                    >
                        <span className="shrink-0 text-[#4a8c70] font-mono">&gt;</span>
                        <span className="flex-1 text-slate-300 truncate">{evt.message}</span>
                        <span className="shrink-0 text-slate-700 tabular-nums">{formatTimestamp(evt.timestamp)}</span>
                    </motion.div>
                ))}
                {computerEvents.length === 0 && (
                    <p className="text-center text-xs text-slate-600 py-6">No computer-use events yet</p>
                )}
            </div>
        </GlassPanel>
    )
}
