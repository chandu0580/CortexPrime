"use client"
import { useEffect, useState } from "react"
import { useRuntimeStore } from "@/store/runtimeStore"
import { runtimeService } from "@/services/runtime"
import { formatLatency } from "@/lib/runtimeHelpers"
import GlowCard from "@/components/ui/GlowCard"
import RuntimeBadge from "@/components/ui/RuntimeBadge"
import SectionHeader from "@/components/ui/SectionHeader"
import RuntimeGrid from "@/components/layout/RuntimeGrid"
import { POLL_INTERVAL_MS } from "@/lib/constants"

// ==========================================
// RUNTIME METRICS
// ==========================================

export default function RuntimeMetrics() {
    const store = useRuntimeStore()
    const [loops, setLoops] = useState(0)

    useEffect(() => {
        const poll = async () => {
            try {
                const r = await runtimeService.getActiveLoops()
                setLoops(r.active_loops?.length ?? 0)
            } catch {}
        }
        poll()
        const t = setInterval(poll, POLL_INTERVAL_MS)
        return () => clearInterval(t)
    }, [])

    const metrics = [
        { label: "Active Agents",  value: store.activeAgents || "—",  unit: "",  color: "purple" as const },
        { label: "Memory",         value: store.memoryUsage,           unit: "",  color: "cyan"   as const },
        { label: "Avg Latency",    value: store.latency,               unit: "",  color: "emerald" as const },
        { label: "Total Events",   value: store.totalEvents || "—",    unit: "",  color: "pink"   as const },
        { label: "Active Loops",   value: loops || "—",                unit: "",  color: "purple" as const },
    ]

    return (
        <div>
            <SectionHeader title="Live System Telemetry" subtitle="Real-time runtime metrics" className="mb-3" />
            <RuntimeGrid cols={3}>
                {metrics.map((m) => (
                    <GlowCard key={m.label} color={m.color} className="text-center">
                        <div className="text-4xl font-black text-[#1a1a1a] tabular-nums leading-none">{m.value}{m.unit}</div>
                        <p className="mt-2 text-sm font-semibold text-[#737373]">{m.label}</p>
                    </GlowCard>
                ))}
            </RuntimeGrid>
            <div className="mt-3 flex items-center gap-2">
                <RuntimeBadge
                    label={store.runtimeStatus}
                    status={store.runtimeStatus === "healthy" ? "active" : store.runtimeStatus === "offline" ? "error" : "degraded"}
                />
                <RuntimeBadge
                    label={store.websocketConnected ? "WebSocket Live" : "WebSocket Offline"}
                    status={store.websocketConnected ? "active" : "error"}
                />
            </div>
        </div>
    )
}
