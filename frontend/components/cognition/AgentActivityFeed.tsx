"use client"
import { motion } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { getAgentColor } from "@/lib/runtimeHelpers"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"

// ==========================================
// AGENT ACTIVITY FEED  —  Live neural states
// ==========================================

export default function AgentActivityFeed() {
    const { agentNodes } = useCognitionStore()

    return (
        <GlassPanel>
            <SectionHeader title="Agent Activity" subtitle="Real-time agent states" />

            <div className="mt-3 space-y-1.5">
                {agentNodes.map((node, i) => {
                    const color    = getAgentColor(node.id)
                    const isActive = node.status === "active" || node.status === "processing"

                    return (
                        <motion.div
                            key={node.id}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.06 }}
                            className="group relative overflow-hidden rounded-lg border border-[#dceee4] bg-[#f0f7f4] px-3 py-2.5 transition-colors hover:border-[#82c0a4]/30 hover:bg-white"
                        >
                            {/* Active left accent bar */}
                            {isActive && (
                                <div
                                    className="absolute left-0 top-0 bottom-0 w-0.5 rounded-r-full"
                                    style={{ background: color, boxShadow: `0 0 6px ${color}` }}
                                />
                            )}

                            <div className="flex items-center gap-2.5">
                                <div className="h-2 w-2 rounded-full shrink-0" style={{ background: isActive ? color : "#d1d1d1" }} />
                                <span className="flex-1 truncate text-sm font-medium text-[#4a4a4a]">
                                    {node.label}
                                </span>
                                <span
                                    className="rounded-full px-1.5 py-0.5 text-xs font-bold uppercase tracking-tight"
                                    style={{
                                        background: `${color}18`,
                                        color,
                                        border: `1px solid ${color}35`,
                                    }}
                                >
                                    {node.status}
                                </span>
                            </div>

                            {/* Processing sweep bar */}
                            {isActive && (
                                <div className="mt-1.5 h-0.5 overflow-hidden rounded-full bg-[#e8f5ee]">
                                    <motion.div
                                        className="h-full rounded-full"
                                        style={{
                                            background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
                                        }}
                                        animate={{ x: ["-100%", "200%"] }}
                                        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                                    />
                                </div>
                            )}
                        </motion.div>
                    )
                })}
            </div>
        </GlassPanel>
    )
}
