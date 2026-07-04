"use client"
import { motion } from "framer-motion"
import { Lightbulb } from "lucide-react"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import { formatRelativeTime } from "@/lib/formatting"
import type { ReflectionEntry } from "@/types/memory"

// ==========================================
// REFLECTION VIEWER
// ==========================================

interface ReflectionViewerProps {
    reflections: ReflectionEntry[]
}

const categoryColor = {
    performance: "#4a8c70",
    knowledge:   "#a855f7",
    strategy:    "#82c0a4",
    correction:  "#f59e0b",
}

export default function ReflectionViewer({ reflections }: ReflectionViewerProps) {
    return (
        <GlassPanel>
            <SectionHeader title="Reflections" subtitle="AI self-improvement insights" />
            <div className="cortex-scroll space-y-2 overflow-y-auto max-h-80">
                {reflections.map((r, i) => {
                    const color = r.category ? categoryColor[r.category] : "#737373"
                    return (
                        <motion.div
                            key={r.id}
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.04 }}
                            className="flex gap-3 rounded-lg border border-[#dceee4] bg-[#f0f7f4] p-3"
                        >
                            <Lightbulb size={13} className="shrink-0 mt-0.5" style={{ color }} />
                            <div>
                                <p className="text-sm text-[#4a4a4a] leading-snug">{r.insight}</p>
                                <div className="mt-1.5 flex items-center gap-2">
                                    {r.category && (
                                        <span className="text-xs font-semibold rounded-full px-1.5 py-0.5" style={{ background: `${color}20`, color }}>
                                            {r.category}
                                        </span>
                                    )}
                                    <span className="text-xs text-[#737373]">{formatRelativeTime(r.timestamp)}</span>
                                </div>
                            </div>
                        </motion.div>
                    )
                })}
                {reflections.length === 0 && (
                    <p className="text-center text-sm text-[#737373] py-6">No reflections yet</p>
                )}
            </div>
        </GlassPanel>
    )
}
