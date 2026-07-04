"use client"
import { motion } from "framer-motion"
import { useRuntimeStore } from "@/store/runtimeStore"
import GlowCard from "@/components/ui/GlowCard"
import RuntimeBadge from "@/components/ui/RuntimeBadge"

// ==========================================
// RUNTIME STATUS CARD
// ==========================================

export default function RuntimeStatusCard() {
    const { runtimeStatus, activeAgents, websocketConnected, totalEvents, latency } = useRuntimeStore()

    const isHealthy = runtimeStatus === "healthy"

    return (
        <GlowCard color={isHealthy ? "emerald" : "pink"} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <span className="text-base font-bold text-[#1a1a1a]">System Status</span>
                <RuntimeBadge
                    label={runtimeStatus}
                    status={isHealthy ? "active" : "degraded"}
                />
            </div>

            <div className="grid grid-cols-2 gap-3">
                {[
                    { label: "Agents",     value: activeAgents },
                    { label: "Events",     value: totalEvents  },
                    { label: "Latency",    value: latency      },
                    { label: "WebSocket",  value: websocketConnected ? "Live" : "Offline" },
                ].map((item) => (
                    <div key={item.label} className="rounded-lg bg-[#f0f7f4] border border-[#e8f5ee] px-3 py-2">
                        <p className="text-xs font-semibold text-[#737373]">{item.label}</p>
                        <p className="text-base font-bold text-[#1a1a1a] tabular-nums">{item.value}</p>
                    </div>
                ))}
            </div>

            <div className="flex items-center gap-2 border-t border-[#e8f5ee] pt-3">
                <div className="w-2 h-2 rounded-full" style={{ background: isHealthy ? "#4a8c70" : "#dc2626" }} />
                <span className="text-xs font-medium text-[#737373]">
                    {isHealthy ? "All systems operational" : "System degraded"}
                </span>
            </div>
        </GlowCard>
    )
}
