"use client"
import { motion } from "framer-motion"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import type { EpisodicMemory } from "@/types/memory"
import { formatRelativeTime } from "@/lib/formatting"

// ==========================================
// EPISODIC VIEWER
// ==========================================

interface EpisodicViewerProps {
    memories: EpisodicMemory[]
}

export default function EpisodicViewer({ memories }: EpisodicViewerProps) {
    return (
        <GlassPanel>
            <SectionHeader title="Episodic Memory" subtitle={`${memories.length} episodes stored`} />
            <div className="cortex-scroll space-y-2 overflow-y-auto max-h-80">
                {memories.map((m, i) => (
                    <motion.div
                        key={m.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                        className="rounded-lg border border-blue-500/15 bg-blue-500/5 p-3"
                    >
                        <p className="text-sm font-medium text-slate-200">{m.event}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{m.context}</p>
                        <p className="text-xs text-slate-500 mt-1">{formatRelativeTime(m.timestamp)}</p>
                    </motion.div>
                ))}
                {memories.length === 0 && (
                    <p className="text-center text-sm text-[#737373] py-6">No episodes stored yet</p>
                )}
            </div>
        </GlassPanel>
    )
}
