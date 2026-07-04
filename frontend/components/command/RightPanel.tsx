"use client"
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    Activity, Radio, Cpu, Database, Zap, Clock,
    AlertCircle, TrendingUp, ChevronDown,
} from "lucide-react"
import { useRealtime } from "@/hooks/useRealtime"
import { useRuntimeStore } from "@/store/runtimeStore"
import {
    AreaChart, Area, ResponsiveContainer, Tooltip,
    LineChart, Line,
} from "recharts"
import LiveFeed from "@/components/command/LiveFeed"

// ==========================================
// METRIC CARD
// ==========================================

function MetricCard({
    label, value, unit, color, icon: Icon, blink = false,
}: {
    label: string; value: string | number; unit?: string; color: string
    icon: React.ElementType; blink?: boolean
}) {
    return (
        <div
            className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-white"
            style={{ border: "1px solid #dceee4", boxShadow: "0 1px 3px rgba(15,23,42,0.04)" }}
        >
            <div className="flex items-center gap-2">
                <Icon size={12} style={{ color }} />
                <span className="text-xs font-semibold text-[#737373]">{label}</span>
            </div>
            <div className="flex items-center gap-1">
                <motion.span
                    key={String(value)}
                    className="text-sm font-bold text-[#1a1a1a]"
                    initial={{ opacity: 0.5, y: -2 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                >
                    {value}
                </motion.span>
                {unit && <span className="text-xs text-[#737373]">{unit}</span>}
                {blink && (
                    <motion.div
                        className="w-1 h-1 rounded-full ml-1"
                        style={{ background: color }}
                        animate={{ opacity: [1, 0.2, 1] }}
                        transition={{ duration: 1.4, repeat: Infinity }}
                    />
                )}
            </div>
        </div>
    )
}

// ==========================================
// COLLAPSIBLE SECTION
// ==========================================

function Section({
    title, icon: Icon, color = "#82c0a4", children, defaultOpen = true,
}: {
    title: string; icon: React.ElementType; color?: string
    children: React.ReactNode; defaultOpen?: boolean
}) {
    const [open, setOpen] = useState(defaultOpen)
    return (
        <div className="mb-1">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between px-3 py-2 transition-colors hover:bg-[#f0f7f4]"
                style={{ borderBottom: "1px solid #e8f5ee" }}
            >
                <div className="flex items-center gap-2">
                    <Icon size={11} style={{ color }} />
                    <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color }}>{title}</span>
                </div>
                <motion.div animate={{ rotate: open ? 0 : -90 }} transition={{ duration: 0.2 }}>
                    <ChevronDown size={10} style={{ color: "#737373" }} />
                </motion.div>
            </button>
            <AnimatePresence initial={false}>
                {open && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.22 }}
                        style={{ overflow: "hidden" }}
                    >
                        <div className="py-2 px-1">{children}</div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

// ==========================================
// RIGHT PANEL
// ==========================================

export default function RightPanel() {
    const { status }                          = useRealtime()
    const {
        activeAgents, runtimeStatus, memoryUsage, totalEvents, latency,
        telemetry, cognitionThroughput,
    } = useRuntimeStore()

    const wsColor = status === "connected" ? "#4a8c70" : status === "connecting" ? "#f9a825" : "#dc2626"
    const wsLabel = status === "connected" ? "Connected" : status === "connecting" ? "Connecting" : "Offline"

    // Map telemetry to chart-friendly format
    const neuralData = telemetry.map((p) => ({ v: p.throughput }))
    const latData    = telemetry.map((p) => ({ v: p.latency }))
    const latLast    = latData[latData.length - 1]?.v ?? 0

    return (
        <div
            className="h-full flex flex-col cortex-scroll overflow-y-auto bg-white"
            style={{ borderLeft: "1px solid #e8f5ee" }}
        >
            {/* Header */}
            <div
                className="flex items-center justify-between px-3 py-3 shrink-0"
                style={{ borderBottom: "1px solid #e8f5ee" }}
            >
                <span className="text-[10px] font-black tracking-widest text-[#82c0a4] uppercase">Telemetry</span>
                <div className="flex items-center gap-1.5">
                    <motion.div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: wsColor }}
                        animate={{ opacity: [1, 0.3, 1] }}
                        transition={{ duration: 1.6, repeat: Infinity }}
                    />
                    <span className="text-xs font-medium" style={{ color: wsColor }}>{wsLabel}</span>
                </div>
            </div>

            {/* -- NEURAL ACTIVITY CHART -- */}
            <Section title="Neural Activity" icon={Activity} color="#82c0a4">
                <div className="px-2">
                    <div className="h-20">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={neuralData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="neuralGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%"   stopColor="#82c0a4" stopOpacity={0.3} />
                                        <stop offset="100%" stopColor="#82c0a4" stopOpacity={0}   />
                                    </linearGradient>
                                </defs>
                                <Area
                                    type="monotone"
                                    dataKey="v"
                                    stroke="#82c0a4"
                                    strokeWidth={1.5}
                                    fill="url(#neuralGrad)"
                                    isAnimationActive={false}
                                />
                                <Tooltip content={() => null} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex justify-between mt-1">
                    <span className="text-xs text-[#737373]">Cognition Throughput</span>
                        <motion.span
                            key={cognitionThroughput}
                            className="text-[9px] font-bold"
                            style={{ color: "#82c0a4" }}
                            initial={{ opacity: 0.5 }}
                            animate={{ opacity: 1 }}
                        >
                            {cognitionThroughput} tok/s
                        </motion.span>
                    </div>
                </div>
            </Section>

            {/* -- LATENCY SPARKLINE -- */}
            <Section title="Latency" icon={TrendingUp} color="#4a8c70">
                <div className="px-2">
                    <div className="h-12">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={latData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                                <Line
                                    type="monotone"
                                    dataKey="v"
                                    stroke="#4a8c70"
                                    strokeWidth={1.2}
                                    dot={false}
                                    isAnimationActive={false}
                                />
                                <Tooltip content={() => null} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex justify-between mt-1">
                    <span className="text-xs text-[#737373]">Response Latency</span>
                        <motion.span
                            key={Math.round(latLast)}
                            className="text-[9px] font-bold text-[#4a8c70]"
                            initial={{ opacity: 0.5, y: -2 }}
                            animate={{ opacity: 1, y: 0 }}
                        >
                            {Math.round(latLast)}ms
                        </motion.span>
                    </div>
                </div>
            </Section>

            {/* -- RUNTIME METRICS -- */}
            <Section title="Runtime Metrics" icon={Cpu} color="#4a8c70">
                <div className="flex flex-col gap-1.5 px-1">
                    <MetricCard label="Latency" value={latency}        color="#82c0a4" icon={Clock}     blink />
                    <MetricCard label="Agents"  value={activeAgents}   color="#4a8c70" icon={Cpu}             />
                    <MetricCard label="Memory"  value={memoryUsage}    color="#4a8c70" icon={Database}        />
                    <MetricCard label="Events"  value={totalEvents.toLocaleString()} color="#4a8c70" icon={Zap} />
                    <MetricCard
                        label="Status"
                        value={runtimeStatus}
                        color={runtimeStatus === "healthy" || runtimeStatus === "Active" ? "#4a8c70" : "#f9a825"}
                        icon={AlertCircle}
                    />
                </div>
            </Section>

            {/* -- LIVE COGNITION FEED -- */}
            <Section title="Event Stream" icon={Radio} color="#4a8c70" defaultOpen>
                <div className="px-1" style={{ height: "220px" }}>
                    <LiveFeed maxItems={20} />
                </div>
            </Section>
        </div>
    )
}