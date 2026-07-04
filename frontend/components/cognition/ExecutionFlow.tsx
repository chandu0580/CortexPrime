"use client"
import { motion } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { getAgentColor } from "@/lib/runtimeHelpers"
import { formatTimestamp } from "@/lib/formatting"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"

// ==========================================
// EXECUTION FLOW
// ==========================================

export default function ExecutionFlow() {
    const { activeTrace } = useCognitionStore()

    if (!activeTrace) {
        return (
            <GlassPanel>
                <SectionHeader title="Execution Flow" />
                    <p className="text-center text-sm text-[#737373] py-6">No active execution</p>
            </GlassPanel>
        )
    }

    return (
        <GlassPanel>
            <SectionHeader
                title="Execution Flow"
                subtitle={activeTrace.goal}
                accent
            />
            <div className="relative space-y-0">
                {activeTrace.phases.map((phase, i) => {
                    const color = getAgentColor(phase.agent)
                    const isLast = i === activeTrace.phases.length - 1
                    return (
                        <div key={i} className="flex gap-3">
                            <div className="flex flex-col items-center">
                                <motion.div
                                    className="h-3 w-3 shrink-0 rounded-full mt-1"
                                    style={{ background: color }}
                                    animate={phase.status === "active"
                                        ? { scale: [1, 1.4, 1], opacity: [0.8, 1, 0.8] }
                                        : {}}
                                    transition={{ duration: 1.5, repeat: Infinity }}
                                />
                                {!isLast && <div className="flex-1 w-px my-1" style={{ background: "#dceee4" }} />}
                            </div>
                            <div className="pb-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-semibold text-[#1a1a1a]">{phase.phase}</span>
                                    <span className="text-xs font-semibold rounded-full px-1.5 py-0.5" style={{ background: `${color}20`, color }}>
                                        {phase.status}
                                    </span>
                                </div>
                                <p className="text-xs font-medium text-[#737373]">{phase.agent}</p>
                                {phase.startedAt && (
                                    <p className="text-xs text-[#737373]">{formatTimestamp(phase.startedAt)}</p>
                                )}
                            </div>
                        </div>
                    )
                })}
            </div>
        </GlassPanel>
    )
}
