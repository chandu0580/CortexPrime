"use client"
import { motion } from "framer-motion"
import { Activity, Zap, Cpu, Radio } from "lucide-react"

// ==========================================
// MOCK RUNTIME PREVIEW
// ==========================================

const MOCK_MESSAGES = [
    { role: "user",      content: "Research the latest AGI safety techniques and create an implementation plan." },
    { role: "system",    content: "PLANNER → decomposing mission into 4 sub-tasks..." },
    { role: "system",    content: "RESEARCHER → executing web search: 'AGI safety 2025 techniques'" },
    { role: "assistant", content: "Analyzing 14 sources... Identified 3 primary frameworks: Constitutional AI, RLHF alignment, and interpretability tooling." },
    { role: "system",    content: "CRITIC → evaluating research quality — confidence: 94%" },
    { role: "system",    content: "OPTIMIZER → refining response structure for clarity..." },
    { role: "assistant", content: "**Mission Complete** — Full implementation roadmap stored in episodic memory. 6 action items generated.", streaming: true },
]

const AGENTS = [
    { name: "PLANNER",     status: "IDLE",   color: "#82c0a4" },
    { name: "RESEARCHER",  status: "ACTIVE", color: "#82c0a4" },
    { name: "CRITIC",      status: "QUEUED", color: "#f59e0b" },
    { name: "OPTIMIZER",   status: "IDLE",   color: "#82c0a4" },
    { name: "ORCHESTRATOR",status: "ACTIVE", color: "#82c0a4" },
]

export default function LivePreviewSection() {
    return (
        <section id="preview" className="relative py-32 px-8 overflow-hidden">
            {/* Ambient */}
            <div className="absolute inset-0 pointer-events-none"
                style={{ background: "radial-gradient(ellipse at 50% 60%, rgba(14,165,233,0.04) 0%, transparent 60%)" }} />

            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <motion.div
                    className="mb-12"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="glyph-mono text-[10px] tracking-widest text-[#82c0a4] mb-3">
                        ── LIVE RUNTIME PREVIEW ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl">
                        <span className="text-gradient-blue">COGNITION</span>
                        {" "}
                        <span className="text-gradient-platinum">IN MOTION</span>
                    </h2>
                </motion.div>

                {/* Mock UI */}
                <motion.div
                    className="relative"
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.1 }}
                    viewport={{ once: true }}
                    style={{ border: "1px solid rgba(14,165,233,0.15)" }}
                >
                    {/* Mock header bar */}
                    <div className="flex items-center justify-between px-4 py-2.5"
                        style={{ background: "#06060f", borderBottom: "1px solid rgba(14,165,233,0.1)" }}>
                        <div className="flex items-center gap-3">
                            <div className="flex gap-1.5">
                                {["#ef4444","#f59e0b","#82c0a4"].map(c => (
                                    <div key={c} className="w-2.5 h-2.5 rounded-full" style={{ background: c, opacity: 0.6 }} />
                                ))}
                            </div>
                            <span className="glyph-mono text-[10px] tracking-widest text-[#737373]">
                                CORTEXPRIME — COMMAND CENTER
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Radio size={10} className="text-[#82c0a4]" />
                            <span className="glyph-mono text-[9px] text-[#82c0a4]">LIVE</span>
                        </div>
                    </div>

                    {/* Mock 3-panel layout */}
                    <div className="flex" style={{ background: "#030309", minHeight: 420 }}>

                        {/* Left panel */}
                        <div className="w-48 flex-shrink-0 p-3 flex flex-col gap-2"
                            style={{ borderRight: "1px solid rgba(14,165,233,0.08)" }}>
                            <div className="glyph-mono text-[9px] tracking-widest text-[#737373] mb-1">AGENT SYSTEMS</div>
                            {AGENTS.map(({ name, status, color }) => (
                                <div key={name} className="flex items-center justify-between px-2 py-1.5"
                                    style={{ background: "rgba(8,8,26,0.8)", border: "1px solid rgba(14,165,233,0.08)" }}>
                                    <span className="glyph-mono text-[9px] text-[#a3a3a3]">{name}</span>
                                    <span className="glyph-mono text-[8px]" style={{ color }}>{status}</span>
                                </div>
                            ))}
                        </div>

                        {/* Center */}
                        <div className="flex-1 flex flex-col p-4 gap-2 overflow-hidden">
                            {MOCK_MESSAGES.slice(0, 5).map((msg, i) => (
                                <motion.div
                                    key={i}
                                    className="flex gap-2"
                                    initial={{ opacity: 0, y: 6 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.15 }}
                                    viewport={{ once: true }}
                                >
                                    {msg.role === "system" ? (
                                        <div className="flex items-center gap-2 px-2 py-1"
                                            style={{ background: "rgba(14,165,233,0.04)", border: "1px solid rgba(14,165,233,0.1)" }}>
                                            <Zap size={8} className="text-[#82c0a4]" />
                                            <span className="glyph-mono text-[9px] text-[#82c0a4]">{msg.content}</span>
                                        </div>
                                    ) : msg.role === "user" ? (
                                        <div className="ml-auto max-w-[70%] px-3 py-2 text-xs text-[#dceee4]"
                                            style={{ background: "rgba(14,165,233,0.08)", border: "1px solid rgba(14,165,233,0.18)" }}>
                                            {msg.content}
                                        </div>
                                    ) : (
                                        <div className="max-w-[80%] px-3 py-2 text-xs text-[#a3a3a3]"
                                            style={{ background: "rgba(8,8,26,0.8)", border: "1px solid rgba(255,255,255,0.05)" }}>
                                            {msg.content}
                                        </div>
                                    )}
                                </motion.div>
                            ))}
                        </div>

                        {/* Right panel */}
                        <div className="w-48 flex-shrink-0 p-3 flex flex-col gap-3"
                            style={{ borderLeft: "1px solid rgba(14,165,233,0.08)" }}>
                            <div className="glyph-mono text-[9px] tracking-widest text-[#737373] mb-1">TELEMETRY</div>
                            {[
                                { label: "LATENCY",  value: "42ms",  color: "#82c0a4" },
                                { label: "EVENTS",   value: "1,847", color: "#82c0a4" },
                                { label: "MEMORY",   value: "246MB", color: "#4a8c70" },
                                { label: "CPU",      value: "12%",   color: "#82c0a4" },
                            ].map(({ label, value, color }) => (
                                <div key={label} className="flex items-center justify-between px-2 py-1.5"
                                    style={{ background: "rgba(8,8,26,0.8)", border: "1px solid rgba(14,165,233,0.06)" }}>
                                    <span className="glyph-mono text-[9px] text-[#737373]">{label}</span>
                                    <span className="glyph-mono text-[9px] font-bold" style={{ color }}>{value}</span>
                                </div>
                            ))}

                            {/* Mini activity bars */}
                            <div className="mt-2">
                                <div className="glyph-mono text-[9px] text-[#737373] mb-2">NEURAL ACTIVITY</div>
                                {[0.8, 0.4, 0.9, 0.6, 0.3, 0.7].map((h, i) => (
                                    <motion.div
                                        key={i}
                                        className="mb-1 rounded-sm"
                                        style={{ height: 3, background: "#82c0a4", width: `${h * 100}%`, opacity: 0.6 }}
                                        animate={{ width: [`${h * 100}%`, `${(h + 0.1) * 100}%`, `${h * 100}%`] }}
                                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Mock input bar */}
                    <div className="flex items-center gap-3 px-4 py-3"
                        style={{ background: "#06060f", borderTop: "1px solid rgba(14,165,233,0.1)" }}>
                        <Cpu size={12} className="text-[#82c0a4]" />
                        <div className="flex-1 glyph-mono text-xs text-[#1e293b]">
                            Enter mission directive...
                        </div>
                        <Activity size={12} className="text-[#82c0a4] animate-blink" />
                    </div>

                    {/* Scan overlay */}
                    <div className="absolute inset-0 pointer-events-none overflow-hidden">
                        <motion.div
                            className="absolute left-0 right-0 h-px"
                            style={{ background: "linear-gradient(90deg, transparent, rgba(14,165,233,0.3), transparent)" }}
                            animate={{ top: ["0%", "100%"] }}
                            transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                        />
                    </div>
                </motion.div>
            </div>
        </section>
    )
}
