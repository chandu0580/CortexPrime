"use client"
import { motion } from "framer-motion"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import type { SemanticMemory } from "@/types/memory"

// ==========================================
// SEMANTIC MEMORY
// ==========================================

interface SemanticMemoryProps {
    memories: SemanticMemory[]
}

export default function SemanticMemoryPanel({ memories }: SemanticMemoryProps) {
    return (
        <GlassPanel>
            <SectionHeader title="Semantic Memory" subtitle="Structured knowledge graph" accent />
            <div className="cortex-scroll space-y-2 overflow-y-auto max-h-80">
                {memories.map((m, i) => (
                    <motion.div
                        key={m.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.04 }}
                        className="rounded-lg border border-[#82c0a4]/15 bg-[#82c0a4]/5 p-3"
                    >
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-[#96cead]">{m.concept}</span>
                            {m.confidence !== undefined && (
                                <span className="text-xs font-semibold text-[#737373]">{Math.round(m.confidence * 100)}%</span>
                            )}
                        </div>
                        <p className="text-sm text-[#737373]">{m.definition}</p>
                        {m.relatedConcepts && m.relatedConcepts.length > 0 && (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                                {m.relatedConcepts.map((c) => (
                                    <span key={c} className="rounded-full bg-[#e8f5ee] px-1.5 py-0.5 text-xs font-medium text-[#737373]">
                                        {c}
                                    </span>
                                ))}
                            </div>
                        )}
                    </motion.div>
                ))}
                {memories.length === 0 && (
                    <p className="text-center text-sm text-[#737373] py-6">No semantic memories yet</p>
                )}
            </div>
        </GlassPanel>
    )
}
