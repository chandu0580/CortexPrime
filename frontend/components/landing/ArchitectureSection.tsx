"use client"
import { motion } from "framer-motion"

// ==========================================
// ARCHITECTURE SECTION
// ==========================================

const LAYERS = [
    {
        id: "frontend",
        label: "FRONTEND RUNTIME",
        desc: "Next.js · React · TypeScript · Zustand · Framer Motion · ReactFlow",
        color: "#82c0a4",
        width: "100%",
    },
    {
        id: "api",
        label: "FASTAPI GATEWAY",
        desc: "REST API · WebSocket Event Bus · Authentication · Rate Limiting",
        color: "#82c0a4",
        width: "82%",
    },
    {
        id: "orchestrator",
        label: "ORCHESTRATION ENGINE",
        desc: "Mission Planner · Agent Registry · LangGraph Runtime · State Manager",
        color: "#4a8c70",
        width: "70%",
    },
    {
        id: "agents",
        label: "COGNITIVE AGENT LAYER",
        desc: "Planner · Researcher · Critic · Optimizer · Orchestrator",
        color: "#82c0a4",
        width: "60%",
    },
    {
        id: "llm",
        label: "LLM ROUTER",
        desc: "OpenAI · Anthropic · Google Gemini · Ollama (local)",
        color: "#82c0a4",
        width: "50%",
    },
    {
        id: "memory",
        label: "MEMORY ARCHITECTURE",
        desc: "Episodic · Semantic · Short-term · Vector (Chroma)",
        color: "#4a8c70",
        width: "45%",
    },
    {
        id: "tools",
        label: "TOOL EXECUTION LAYER",
        desc: "Browser (Playwright) · Desktop (PyAutoGUI) · Vision (OCR) · Voice",
        color: "#82c0a4",
        width: "38%",
    },
]

export default function ArchitectureSection() {
    return (
        <section id="architecture" className="relative py-32 px-8 overflow-hidden">
            {/* Background grid */}
            <div className="absolute inset-0 hex-dot-bg opacity-40 pointer-events-none" />

            <div className="relative z-10 max-w-5xl mx-auto">
                {/* Header */}
                <motion.div
                    className="mb-16"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="glyph-mono text-[10px] tracking-widest text-[#82c0a4] mb-3">
                        ── RUNTIME ARCHITECTURE ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl leading-tight">
                        <span className="text-gradient-blue">SYSTEM</span>
                        {" "}
                        <span className="text-gradient-platinum">LAYERS</span>
                    </h2>
                </motion.div>

                {/* Architecture pyramid */}
                <div className="flex flex-col gap-2">
                    {LAYERS.map((layer, i) => (
                        <motion.div
                            key={layer.id}
                            className="relative group mx-auto"
                            style={{ width: layer.width }}
                            initial={{ opacity: 0, x: -30 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.5, delay: i * 0.08 }}
                            viewport={{ once: true }}
                        >
                            <div
                                className="flex items-center justify-between px-5 py-3 cursor-default transition-all duration-200"
                                style={{
                                    background: `rgba(8,8,26,0.9)`,
                                    border: `1px solid ${layer.color}22`,
                                    borderLeft: `3px solid ${layer.color}`,
                                }}
                            >
                                <div className="glyph-mono text-xs font-bold tracking-wider" style={{ color: layer.color }}>
                                    {layer.label}
                                </div>
                                <div className="text-[10px] text-[#737373] hidden md:block">
                                    {layer.desc}
                                </div>
                            </div>

                            {/* Connecting arrow */}
                            {i < LAYERS.length - 1 && (
                                <div className="flex justify-center mt-1">
                                    <div className="w-px h-2" style={{ background: `${layer.color}40` }} />
                                </div>
                            )}
                        </motion.div>
                    ))}
                </div>

                {/* Connection legend */}
                <motion.div
                    className="mt-12 flex flex-wrap gap-6 justify-center"
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    transition={{ duration: 0.6, delay: 0.5 }}
                    viewport={{ once: true }}
                >
                    {[
                        { label: "HTTP REST", color: "#82c0a4" },
                        { label: "WebSocket", color: "#82c0a4" },
                        { label: "Event Bus", color: "#4a8c70" },
                        { label: "LangGraph", color: "#82c0a4" },
                    ].map(({ label, color }) => (
                        <div key={label} className="flex items-center gap-2">
                            <div className="w-6 h-px" style={{ background: color }} />
                            <span className="glyph-mono text-[10px] tracking-wider" style={{ color: "#737373" }}>{label}</span>
                        </div>
                    ))}
                </motion.div>
            </div>
        </section>
    )
}
