"use client"
import { motion } from "framer-motion"
import { Activity, Zap, Cpu, Database, Network, Target } from "lucide-react"

// ==========================================
// METRIC DEFINITIONS
// ==========================================

const METRICS = [
    { icon: Zap,      label: "RESPONSE LATENCY",   value: "42ms",    subtext: "avg across agents",  color: "#82c0a4", bars: [0.3,0.55,0.4,0.7,0.5,0.65,0.42,0.58,0.45,0.60] },
    { icon: Activity, label: "EVENTS / SECOND",    value: "1,847",   subtext: "live event bus",     color: "#4a8c70", bars: [0.5,0.75,0.9,0.6,0.8,0.95,0.7,0.85,0.78,0.92] },
    { icon: Database, label: "MEMORY USED",        value: "246 MB",  subtext: "working + vector",   color: "#4a8c70", bars: [0.6,0.62,0.65,0.63,0.68,0.70,0.72,0.74,0.73,0.75] },
    { icon: Cpu,      label: "CPU UTILIZATION",    value: "12%",     subtext: "all cores",          color: "#82c0a4", bars: [0.1,0.15,0.12,0.18,0.14,0.11,0.16,0.13,0.17,0.12] },
    { icon: Network,  label: "ACTIVE AGENTS",      value: "3 / 7",   subtext: "concurrent",         color: "#4a8c70", bars: [0.4,0.4,0.57,0.57,0.43,0.43,0.57,0.57,0.43,0.43] },
    { icon: Target,   label: "MISSIONS COMPLETE",  value: "12,847",  subtext: "all time",           color: "#4a8c70", bars: [0.6,0.65,0.7,0.72,0.75,0.78,0.82,0.85,0.88,0.92] },
]

// ==========================================
// SPARKLINE
// ==========================================

function Sparkline({ bars, color, animated }: { bars: number[]; color: string; animated: boolean }) {
    return (
        <div className="flex items-end gap-0.5" style={{ height: 32 }}>
            {bars.map((h, i) => (
                <motion.div
                    key={i}
                    className="flex-1 rounded-sm"
                    style={{ background: `${color}40` }}
                    initial={{ scaleY: 0, originY: 1 }}
                    animate={animated ? { scaleY: [h, h * 1.12, h * 0.94, h], opacity: [0.5, 0.9, 0.7, 0.5] } : { scaleY: h }}
                    transition={animated
                        ? { duration: 2.4 + i * 0.18, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }
                        : { duration: 0.6, delay: i * 0.06 }}
                />
            ))}
        </div>
    )
}

// ==========================================
// METRIC CARD — Light
// ==========================================

function MetricCard({ icon: Icon, label, value, subtext, color, bars, index }: {
    icon: React.ElementType; label: string; value: string; subtext: string; color: string; bars: number[]; index: number
}) {
    return (
        <motion.div
            className="group relative flex flex-col gap-4 p-5 bg-white rounded-2xl cursor-default"
            style={{ border: "1px solid #dceee4", boxShadow: "0 2px 8px rgba(15,23,42,0.04)" }}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: index * 0.07 }}
            viewport={{ once: true }}
            whileHover={{ borderColor: `${color}40`, boxShadow: `0 8px 24px rgba(15,23,42,0.08)`, y: -2 }}
        >
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center justify-center w-9 h-9 rounded-lg" style={{ background: `${color}10`, border: `1px solid ${color}25` }}>
                    <Icon size={16} style={{ color }} />
                </div>
                <div className="flex items-center gap-1.5">
                    <motion.div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: color }}
                        animate={{ opacity: [1, 0.3, 1] }}
                        transition={{ duration: 1.8, repeat: Infinity, delay: index * 0.2 }}
                    />
                    <span className="text-[9px] glyph-mono font-bold tracking-widest" style={{ color: `${color}99` }}>LIVE</span>
                </div>
            </div>

            {/* Value */}
            <div>
                <div className="font-black text-2xl leading-none text-[#1a1a1a]">{value}</div>
                <div className="text-[10px] text-[#a3a3a3] mt-1">{subtext}</div>
            </div>

            <Sparkline bars={bars} color={color} animated />

            <div className="text-[9px] glyph-mono font-bold tracking-widest" style={{ color: `${color}70` }}>{label}</div>
        </motion.div>
    )
}

// ==========================================
// TELEMETRY SECTION — Premium Light
// ==========================================

export default function TelemetrySection() {
    return (
        <section id="telemetry" className="relative py-28 px-8 overflow-hidden" style={{ background: "#ffffff" }}>
            {/* Dividers */}
            <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(74,140,112,0.15), transparent)" }} />
            <div className="absolute bottom-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(130,192,164,0.15), transparent)" }} />

            <div className="relative z-10 max-w-6xl mx-auto">
                {/* Header */}
                <motion.div
                    className="mb-14"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="text-[10px] glyph-mono tracking-widest text-[#4a8c70] mb-3 font-semibold uppercase">
                        ── Runtime Telemetry ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl text-[#1a1a1a]">
                        System <span className="text-gradient-blue">Metrics</span>
                    </h2>
                    <p className="mt-4 text-sm text-[#737373] max-w-xl leading-relaxed">
                        Live runtime telemetry from the CortexPrime cognitive operating system.
                        All metrics stream in real time via the internal event bus.
                    </p>
                </motion.div>

                {/* Metrics grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
                    {METRICS.map((m, i) => <MetricCard key={m.label} {...m} index={i} />)}
                </div>

                {/* System health panel */}
                <motion.div
                    className="relative p-6 bg-white rounded-2xl"
                    style={{ border: "1px solid #dceee4", boxShadow: "0 4px 16px rgba(15,23,42,0.06)" }}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.3 }}
                    viewport={{ once: true }}
                >
                    <div className="flex flex-col lg:flex-row items-start gap-8">
                        <div className="flex-1">
                            <div className="text-xs font-semibold text-[#737373] mb-4 uppercase tracking-widest">System Health Status</div>
                            <div className="grid grid-cols-2 gap-3">
                                {[
                                    { label: "Cognitive Engine",    status: "Nominal",  color: "#4a8c70" },
                                    { label: "Agent Mesh",          status: "Active",   color: "#4a8c70" },
                                    { label: "Memory Fabric",       status: "Synced",   color: "#82c0a4" },
                                    { label: "LLM Router",          status: "Ready",    color: "#82c0a4" },
                                    { label: "Event Bus",           status: "Live",     color: "#4a8c70" },
                                    { label: "WebSocket Gateway",   status: "Open",     color: "#4a8c70" },
                                ].map(({ label, status, color }) => (
                                    <div key={label} className="flex items-center justify-between px-3 py-2.5 rounded-lg"
                                        style={{ background: "#f0f7f4", border: "1px solid #dceee4" }}>
                                        <span className="text-xs text-[#737373]">{label}</span>
                                        <div className="flex items-center gap-1.5">
                                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                                            <span className="text-xs font-semibold" style={{ color }}>{status}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="w-full lg:w-48">
                            <div className="text-xs font-semibold text-[#737373] mb-4 uppercase tracking-widest">System Uptime</div>
                            <div className="text-3xl font-black text-[#1a1a1a] mb-2">99.97%</div>
                            <div className="w-full h-2 rounded-full bg-[#e8f5ee]">
                                <motion.div
                                    className="h-full rounded-full"
                                    style={{ background: "linear-gradient(90deg, #82c0a4, #4a8c70)" }}
                                    initial={{ width: 0 }}
                                    whileInView={{ width: "99.97%" }}
                                    transition={{ duration: 1.5, delay: 0.4, ease: "easeOut" }}
                                    viewport={{ once: true }}
                                />
                            </div>
                            <div className="text-xs text-[#a3a3a3] mt-2">30-day average</div>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    )
}

