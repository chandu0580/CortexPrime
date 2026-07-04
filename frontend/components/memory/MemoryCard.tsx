"use client"
import { motion } from "framer-motion"
import { formatRelativeTime } from "@/lib/formatting"
import { cn } from "@/utils/cn"
import type { MemoryEntry } from "@/types/memory"

// ==========================================
// MEMORY CARD
// ==========================================

interface MemoryCardProps {
    entry: MemoryEntry
    className?: string
}

const typeColor = {
    episodic: { bg: "#4a8c7020", border: "#4a8c7040", text: "#93c5fd" },
    semantic:  { bg: "#a855f720", border: "#a855f740", text: "#d8b4fe" },
    working:   { bg: "#82c0a420", border: "#82c0a440", text: "#6ee7b7" },
}

export default function MemoryCard({ entry, className }: MemoryCardProps) {
    const c = typeColor[entry.type]
    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                "rounded-lg border p-3 transition-colors",
                className
            )}
            style={{ background: c.bg, borderColor: c.border }}
        >
            <div className="flex items-start justify-between gap-2 mb-1">
                <span className="text-xs font-semibold rounded-full px-2 py-0.5" style={{ background: c.border, color: c.text }}>
                    {entry.type}
                </span>
                <span className="text-xs text-slate-500">{formatRelativeTime(entry.timestamp)}</span>
            </div>
            <p className="text-sm text-slate-300 leading-snug">{entry.content}</p>
            {entry.agent && <p className="mt-1 text-xs font-medium text-slate-400">by {entry.agent}</p>}
        </motion.div>
    )
}
