"use client"
import { motion } from "framer-motion"
import { Brain, Database, Cpu, Globe } from "lucide-react"

// ==========================================
// COGNITIVE SYSTEMS SECTION
// ==========================================

const SYSTEMS = [
    {
        icon: Brain,
        title: "Cognition Engine",
        subtitle: "COGNITIVE CORE",
        color: "#82c0a4",
        metrics: [
            { label: "Decision Latency",  value: "< 120ms" },
            { label: "Context Window",    value: "200K tokens" },
            { label: "Agent Parallelism", value: "5 concurrent" },
        ],
        description: "Real-time cognitive orchestration with multi-step reasoning, task decomposition, and dynamic re-planning based on environmental feedback.",
    },
    {
        icon: Database,
        title: "Memory Fabric",
        subtitle: "PERSISTENCE LAYER",
        color: "#82c0a4",
        metrics: [
            { label: "Vector Dimensions", value: "1,536" },
            { label: "Episodic Records",  value: "∞" },
            { label: "Recall Accuracy",   value: "94.2%" },
        ],
        description: "Four-tier memory architecture: episodic (events), semantic (facts), short-term (working), and vector (embedding search) with automatic consolidation.",
    },
    {
        icon: Cpu,
        title: "Orchestrator",
        subtitle: "EXECUTION ENGINE",
        color: "#4a8c70",
        metrics: [
            { label: "Mission Types",    value: "12+" },
            { label: "Max Loop Depth",   value: "32" },
            { label: "Autonomy Level",   value: "FULL" },
        ],
        description: "LangGraph-powered orchestration with dynamic mission trees, automatic retries, agent specialization routing, and human-in-the-loop governance.",
    },
    {
        icon: Globe,
        title: "World Model",
        subtitle: "ENVIRONMENTAL AWARENESS",
        color: "#82c0a4",
        metrics: [
            { label: "Browser Contexts",  value: "Multi-tab" },
            { label: "Desktop Control",   value: "Full OS" },
            { label: "Vision Pipeline",   value: "Real-time" },
        ],
        description: "Persistent environmental state tracking with browser automation, desktop control, screenshot analysis, and OCR for complete situational awareness.",
    },
]

export default function CognitiveSystemsSection() {
    return (
        <section id="systems" className="relative py-32 px-8">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <motion.div
                    className="mb-16"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="glyph-mono text-[10px] tracking-widest text-[#82c0a4] mb-3">
                        ── COGNITIVE SUBSYSTEMS ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl">
                        <span className="text-gradient-green">CORE</span>
                        {" "}
                        <span className="text-gradient-platinum">SYSTEMS</span>
                    </h2>
                </motion.div>

                {/* Systems grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {SYSTEMS.map(({ icon: Icon, title, subtitle, color, metrics, description }, i) => (
                        <motion.div
                            key={title}
                            className="group relative p-6 cursor-default"
                            style={{
                                background: "rgba(6,6,15,0.95)",
                                border: `1px solid ${color}18`,
                            }}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.5, delay: i * 0.1 }}
                            viewport={{ once: true }}
                            whileHover={{ borderColor: `${color}35`, background: "rgba(8,8,26,0.98)" }}
                        >
                            {/* Corner glyphs */}
                            <div className="absolute top-0 right-0 w-12 h-px" style={{ background: `${color}50` }} />
                            <div className="absolute top-0 right-0 w-px h-12" style={{ background: `${color}50` }} />

                            {/* Header */}
                            <div className="flex items-start gap-4 mb-5">
                                <div
                                    className="flex items-center justify-center w-12 h-12 flex-shrink-0"
                                    style={{ background: `${color}0d`, border: `1px solid ${color}30` }}
                                >
                                    <Icon size={20} style={{ color }} />
                                </div>
                                <div>
                                    <div className="glyph-mono text-[9px] tracking-widest mb-1" style={{ color: `${color}80` }}>
                                        {subtitle}
                                    </div>
                                    <h3 className="font-black text-lg text-[#dceee4]">{title}</h3>
                                </div>
                            </div>

                            {/* Metrics row */}
                            <div className="flex gap-4 mb-5 pb-5" style={{ borderBottom: `1px solid rgba(255,255,255,0.04)` }}>
                                {metrics.map(({ label, value }) => (
                                    <div key={label} className="flex flex-col gap-0.5">
                                        <div className="glyph-mono font-bold text-sm" style={{ color }}>
                                            {value}
                                        </div>
                                        <div className="glyph-mono text-[9px] tracking-wider text-[#737373]">
                                            {label}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Description */}
                            <p className="text-xs text-[#737373] leading-relaxed group-hover:text-[#737373] transition-colors">
                                {description}
                            </p>

                            {/* Active bar */}
                            <div
                                className="absolute bottom-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                                style={{ background: `linear-gradient(90deg, transparent, ${color}60, transparent)` }}
                            />
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
