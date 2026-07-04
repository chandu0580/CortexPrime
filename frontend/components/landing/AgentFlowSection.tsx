"use client"
import { motion } from "framer-motion"
import { Brain, Search, MessageSquare, TrendingUp, Database, RefreshCw, Network } from "lucide-react"

// ==========================================
// AGENTS
// ==========================================

const AGENTS = [
    {
        id: "orchestrator",
        name: "ORCHESTRATOR",
        role: "Mission Command",
        icon: Network,
        color: "#82c0a4",
        status: "ACTIVE",
        desc: "Coordinates all agents, manages mission state, and routes tasks to specialized subsystems.",
        row: 0,
        col: 3,
    },
    {
        id: "planner",
        name: "PLANNER",
        role: "Task Decomposition",
        icon: Brain,
        color: "#4a8c70",
        status: "STANDBY",
        desc: "Decomposes complex missions into executable sub-tasks with priority ordering.",
        row: 1,
        col: 1,
    },
    {
        id: "researcher",
        name: "RESEARCHER",
        role: "Knowledge Retrieval",
        icon: Search,
        color: "#4a8c70",
        status: "ACTIVE",
        desc: "Executes web searches, reads documents, and synthesizes information from diverse sources.",
        row: 1,
        col: 3,
    },
    {
        id: "critic",
        name: "CRITIC",
        role: "Quality Validation",
        icon: MessageSquare,
        color: "#82c0a4",
        status: "QUEUED",
        desc: "Evaluates agent outputs for accuracy, coherence, and alignment with mission objectives.",
        row: 1,
        col: 5,
    },
    {
        id: "optimizer",
        name: "OPTIMIZER",
        role: "Output Refinement",
        icon: TrendingUp,
        color: "#82c0a4",
        status: "STANDBY",
        desc: "Refines and improves agent responses, optimizing for clarity, precision, and efficiency.",
        row: 2,
        col: 2,
    },
    {
        id: "memory",
        name: "MEMORY",
        role: "Persistence Layer",
        icon: Database,
        color: "#4a8c70",
        status: "ACTIVE",
        desc: "Manages episodic, semantic, short-term, and vector memory with automatic consolidation.",
        row: 2,
        col: 4,
    },
    {
        id: "reflection",
        name: "REFLECTION",
        role: "Self-Improvement",
        icon: RefreshCw,
        color: "#82c0a4",
        status: "IDLE",
        desc: "Analyzes past mission performance and generates insights for continuous system improvement.",
        row: 3,
        col: 3,
    },
]

const STATUS_COLOR: Record<string, string> = {
    ACTIVE:  "#4a8c70",
    STANDBY: "#82c0a4",
    QUEUED:  "#f9a825",
    IDLE:    "#a3a3a3",
}

// Connection pairs: [from, to]
const CONNECTIONS = [
    ["orchestrator", "planner"],
    ["orchestrator", "researcher"],
    ["orchestrator", "critic"],
    ["planner",      "optimizer"],
    ["critic",       "optimizer"],
    ["optimizer",    "memory"],
    ["researcher",   "memory"],
    ["memory",       "reflection"],
]

// ==========================================
// AGENT CARD
// ==========================================

function AgentCard({
    agent,
    index,
}: {
    agent: typeof AGENTS[number]
    index: number
}) {
    const { icon: Icon, name, role, color, status, desc } = agent

    return (
        <motion.div
            className="group relative flex flex-col gap-3 p-5 cursor-default select-none bg-white rounded-xl"
            style={{
                border: `1px solid #dceee4`,
                boxShadow: "0 2px 8px rgba(15,23,42,0.05)",
                minWidth: 180,
                maxWidth: 220,
            }}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.06 * index }}
            viewport={{ once: true }}
            whileHover={{ borderColor: `${color}50`, boxShadow: `0 8px 20px rgba(15,23,42,0.1), 0 0 0 1px ${color}25`, y: -2 }}
        >
            {/* Top-left corner accent */}
            <div className="absolute top-0 left-0 w-8 h-px" style={{ background: color }} />
            <div className="absolute top-0 left-0 w-px h-8" style={{ background: color }} />
            {/* Bottom-right corner accent */}
            <div className="absolute bottom-0 right-0 w-8 h-px" style={{ background: `${color}60` }} />
            <div className="absolute bottom-0 right-0 w-px h-8" style={{ background: `${color}60` }} />

            {/* Status + Icon row */}
            <div className="flex items-center justify-between">
                <div
                    className="flex items-center justify-center w-9 h-9"
                    style={{ background: `${color}0d`, border: `1px solid ${color}30` }}
                >
                    <Icon size={16} style={{ color }} />
                </div>
                <div className="flex items-center gap-1.5">
                    <motion.div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: STATUS_COLOR[status] ?? "#737373" }}
                        animate={status === "ACTIVE" ? { opacity: [1, 0.3, 1] } : {}}
                        transition={{ duration: 1.2, repeat: Infinity }}
                    />
                    <span
                        className="glyph-mono text-[8px] font-bold tracking-widest"
                        style={{ color: STATUS_COLOR[status] ?? "#737373" }}
                    >
                        {status}
                    </span>
                </div>
            </div>

            {/* Name + Role */}
            <div>
                <div className="glyph-mono font-black text-xs tracking-widest text-[#1a1a1a]">
                    {name}
                </div>
                <div className="glyph-mono text-[9px] tracking-wider mt-0.5" style={{ color: `${color}90` }}>
                    {role}
                </div>
            </div>

            {/* Description */}
            <p className="text-[10px] leading-relaxed text-[#737373] group-hover:text-[#4a4a4a] transition-colors">
                {desc}
            </p>

            {/* Bottom glow line on hover */}
            <div
                className="absolute bottom-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{ background: `linear-gradient(90deg, transparent, ${color}80, transparent)` }}
            />
        </motion.div>
    )
}

// ==========================================
// FLOW CONNECTOR (animated line)
// ==========================================

function FlowLine({ delay = 0, color = "#82c0a4", vertical = false }: { delay?: number; color?: string; vertical?: boolean }) {
    return (
        <motion.div
            className="relative overflow-hidden"
            style={
                vertical
                    ? { width: 1, height: 40, background: `${color}18` }
                    : { height: 1, width: 60, background: `${color}18` }
            }
        >
            <motion.div
                className="absolute"
                style={
                    vertical
                        ? { top: 0, left: 0, width: "100%", height: 12, background: `linear-gradient(to bottom, transparent, ${color}, transparent)` }
                        : { top: 0, left: 0, height: "100%", width: 20, background: `linear-gradient(to right, transparent, ${color}, transparent)` }
                }
                animate={vertical ? { top: ["-20px", "100%"] } : { left: ["-20px", "100%"] }}
                transition={{ duration: 1.8, repeat: Infinity, delay, ease: "linear" }}
            />
        </motion.div>
    )
}

// ==========================================
// AGENT FLOW SECTION
// ==========================================

export default function AgentFlowSection() {
    return (
        <section id="agents" className="relative py-28 px-8 overflow-hidden" style={{ background: "#f0f7f4" }}>
            {/* Background */}
            <div className="absolute inset-0 hex-dot-bg opacity-40 pointer-events-none" />
            <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(130,192,164,0.18), transparent)" }} />

            <div className="relative z-10 max-w-6xl mx-auto">

                {/* Header */}
                <motion.div
                    className="mb-16"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="text-[10px] glyph-mono tracking-widest text-[#4a8c70] mb-3 font-semibold uppercase">
                        ── Multi-Agent Architecture ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl leading-tight text-[#1a1a1a]">
                        Cognitive <span className="text-gradient-blue">Agent Mesh</span>
                    </h2>
                    <p className="mt-4 text-sm text-[#737373] max-w-xl leading-relaxed">
                        Seven specialized agents operate in coordinated execution under a central orchestrator,
                        forming a self-improving cognitive mesh.
                    </p>
                </motion.div>

                {/* Row 0: Orchestrator */}
                <div className="flex flex-col items-center gap-0">
                    <div className="flex justify-center">
                        <AgentCard agent={AGENTS[0]} index={0} />
                    </div>

                    {/* Down + spread connectors */}
                    <div className="flex justify-center gap-0 w-full">
                        <div className="flex items-start justify-center gap-0 w-full max-w-2xl">
                            {/* Left line to planner */}
                            <div className="flex-1 flex flex-col items-end pt-0">
                                <FlowLine delay={0.1} color="#82c0a4" vertical />
                                <div className="h-px flex-1 self-stretch" style={{ background: "rgba(14,165,233,0.15)", maxWidth: "50%" }} />
                            </div>
                            {/* Center line to researcher */}
                            <FlowLine delay={0.3} color="#4a8c70" vertical />
                            {/* Right line to critic */}
                            <div className="flex-1 flex flex-col items-start pt-0">
                                <FlowLine delay={0.5} color="#82c0a4" vertical />
                            </div>
                        </div>
                    </div>

                    {/* Row 1: Planner, Researcher, Critic */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-3xl">
                        {AGENTS.slice(1, 4).map((agent, i) => (
                            <AgentCard key={agent.id} agent={agent} index={i + 1} />
                        ))}
                    </div>

                    {/* Converging connector */}
                    <div className="flex justify-center w-full max-w-3xl">
                        <div className="grid grid-cols-3 w-full gap-4">
                            {[0.2, 0.4, 0.6].map((d, i) => (
                                <div key={i} className="flex justify-center">
                                    <FlowLine delay={d} color={i === 1 ? "#4a8c70" : "#82c0a4"} vertical />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Row 2: Optimizer + Memory */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-xl">
                        {AGENTS.slice(4, 6).map((agent, i) => (
                            <AgentCard key={agent.id} agent={agent} index={i + 4} />
                        ))}
                    </div>

                    {/* Down connector to reflection */}
                    <div className="flex justify-center gap-4">
                        <FlowLine delay={0.3} color="#82c0a4" vertical />
                        <FlowLine delay={0.6} color="#4a8c70" vertical />
                    </div>

                    {/* Row 3: Reflection */}
                    <div className="flex justify-center">
                        <AgentCard agent={AGENTS[6]} index={6} />
                    </div>
                </div>

                {/* Legend */}
                <motion.div
                    className="mt-12 flex flex-wrap justify-center gap-8"
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    transition={{ duration: 0.6, delay: 0.4 }}
                    viewport={{ once: true }}
                >
                    {Object.entries(STATUS_COLOR).map(([status, color]) => (
                        <div key={status} className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                            <span className="glyph-mono text-[9px] tracking-widest text-[#737373]">{status}</span>
                        </div>
                    ))}
                </motion.div>
            </div>
        </section>
    )
}
