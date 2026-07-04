"use client"
import { motion } from "framer-motion"
import { useRuntimeStore } from "@/store/runtimeStore"
import { useRealtime } from "@/hooks/useRealtime"
import { Cpu, Zap, Activity, Layers } from "lucide-react"

// ==========================================
// RUNTIME HEADER  —  Command-center HUD
// ==========================================

export default function RuntimeHeader() {
    const { activeAgents, runtimeStatus, totalEvents, latency } = useRuntimeStore()
    const { status } = useRealtime()

    const isLive    = status === "connected"
    const isHealthy = runtimeStatus === "healthy" || runtimeStatus === "Active"

    const stats = [
        { icon: Cpu,      label: "Agents",  value: activeAgents,   color: "#82c0a4" },
        { icon: Activity, label: "Events",  value: totalEvents,    color: "#4a8c70" },
        { icon: Zap,      label: "Latency", value: latency,        color: "#82c0a4" },
        { icon: Layers,   label: "Status",  value: runtimeStatus,  color: isHealthy ? "#4a8c70" : "#f9a825" },
    ]

    return (
        <div className="relative mb-5 overflow-hidden rounded-xl px-6 py-4 bg-white" style={{ border: "1px solid #dceee4" }}>
            {/* Top accent line */}
            <div className="pointer-events-none absolute inset-x-0 top-0 h-0.5 rounded-t-xl" style={{ background: "linear-gradient(90deg, transparent, #82c0a4, transparent)" }} />

            <div className="relative flex items-center justify-between gap-6">

                {/* ── Left: Branding ── */}
                <div className="shrink-0">
                    <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4 }}
                        className="flex items-center gap-2.5"
                    >
                        <h1 className="text-3xl font-black tracking-tight" style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                            CortexPrime
                        </h1>
                        {/* Live badge */}
                        <div style={isLive
                            ? { display: "flex", alignItems: "center", gap: "6px", borderRadius: "9999px", border: "1px solid #bbf7d0", background: "#f0fdf4", padding: "2px 10px" }
                            : { display: "flex", alignItems: "center", gap: "6px", borderRadius: "9999px", border: "1px solid #fecaca", background: "#fef2f2", padding: "2px 10px" }
                        }>
                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: isLive ? "#4a8c70" : "#dc2626" }} />
                            <span className="text-xs font-bold uppercase tracking-widest" style={{ color: isLive ? "#4a8c70" : "#dc2626" }}>
                                {isLive ? "Live" : "Offline"}
                            </span>
                        </div>
                    </motion.div>
                    <p className="mt-0.5 text-sm font-medium text-[#737373]">Autonomous AI Execution Platform</p>
                </div>

                {/* ── Center: spacer ── */}
                <div className="hidden lg:block flex-1" />

                {/* ── Right: Stats ── */}
                <div className="flex shrink-0 items-center gap-5">
                    {stats.map(({ icon: Icon, label, value, color }, i) => (
                        <motion.div
                            key={label}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.07 }}
                            className="flex flex-col items-end gap-0.5"
                        >
                            <div className="flex items-center gap-1.5">
                                <Icon size={11} style={{ color }} />
                                <span
                                    className="text-base font-bold tabular-nums"
                                    style={{ color }}
                                >
                                    {value}
                                </span>
                            </div>
                            <span className="text-xs font-medium text-[#737373]">{label}</span>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    )
}
