"use client"
import { motion } from "framer-motion"
import { formatRelativeTime } from "@/lib/formatting"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import type { MemoryEntry } from "@/types/memory"

// ==========================================
// MEMORY TIMELINE
// ==========================================

interface MemoryTimelineProps {
    entries: MemoryEntry[]
}

export default function MemoryTimeline({ entries }: MemoryTimelineProps) {
    return (
        <GlassPanel>
            <SectionHeader title="Memory Timeline" subtitle="Chronological memory formation" accent />
            <div className="cortex-scroll relative max-h-96 overflow-y-auto space-y-0">
                {entries.map((entry, i) => (
                    <div key={entry.id} className="flex gap-3">
                        <div className="flex flex-col items-center">
                            <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-[#82c0a4]/60" />
                            {i < entries.length - 1 && <div className="flex-1 w-px bg-[#dceee4] my-1" />}
                        </div>
                        <motion.div
                            initial={{ opacity: 0, x: -6 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.04 }}
                            className="pb-3 min-w-0"
                        >
                            <p className="text-sm text-slate-300 leading-snug">{entry.content}</p>
                            <span className="text-xs text-slate-500">{formatRelativeTime(entry.timestamp)}</span>
                        </motion.div>
                    </div>
                ))}
                {entries.length === 0 && (
                    <p className="text-center text-sm text-[#737373] py-6">No memories formed yet</p>
                )}
            </div>
        </GlassPanel>
    )
}
