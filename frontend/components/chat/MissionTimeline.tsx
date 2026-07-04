"use client"
import { motion } from "framer-motion"
import { CheckCircle, Clock, Loader } from "lucide-react"
import { formatRelativeTime } from "@/lib/formatting"
import { cn } from "@/utils/cn"
import type { Mission } from "@/types/runtime"

// ==========================================
// MISSION TIMELINE
// ==========================================

interface MissionTimelineProps {
    missions: Mission[]
}

const statusIcon = {
    active:    <Loader size={13} className="animate-spin text-blue-400" />,
    completed: <CheckCircle size={13} className="text-emerald-400" />,
    failed:    <CheckCircle size={13} className="text-red-400" />,
    pending:   <Clock size={13} className="text-amber-400" />,
}

export default function MissionTimeline({ missions }: MissionTimelineProps) {
    if (!missions.length) {
        return (
            <p className="text-center text-xs text-slate-600 py-6">No missions yet</p>
        )
    }

    return (
        <div className="space-y-2">
            {missions.map((m, i) => (
                <motion.div
                    key={m.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={cn(
                        "flex items-start gap-3 rounded-lg border p-3",
                        m.status === "active"
                            ? "border-blue-500/20 bg-blue-500/5"
                            : m.status === "completed"
                            ? "border-emerald-500/15 bg-emerald-500/5"
                            : "border-white/5 bg-white/2"
                    )}
                >
                    <span className="mt-0.5 shrink-0">{statusIcon[m.status]}</span>
                    <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-slate-200">{m.goal}</p>
                        <p className="text-[10px] text-slate-600">{formatRelativeTime(m.createdAt)}</p>
                    </div>
                </motion.div>
            ))}
        </div>
    )
}
