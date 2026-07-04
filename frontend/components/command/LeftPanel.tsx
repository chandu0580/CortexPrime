"use client"
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    Brain, Search, AlertCircle, TrendingUp, Network, ChevronDown,
    Play, Square, RefreshCw, Database, Layers, MemoryStick,
} from "lucide-react"
import { useRuntimeStore } from "@/store/runtimeStore"
import { useMissionStore } from "@/store/missionStore"
import type { AgentActivityStatus } from "@/store/runtimeStore"

// ==========================================
// AGENT DEFINITIONS
// ==========================================

const AGENTS = [
    { id: "orchestrator", name: "ORCHESTRATOR", icon: Network,      role: "Agent coordination & mission control" },
    { id: "planner",      name: "PLANNER",      icon: Brain,        role: "Mission decomposition & task trees"  },
    { id: "research",     name: "RESEARCHER",   icon: Search,       role: "Autonomous web & knowledge search"   },
    { id: "critic",       name: "CRITIC",       icon: AlertCircle,  role: "Output validation & quality control" },
    { id: "optimizer",    name: "OPTIMIZER",    icon: TrendingUp,   role: "Response refinement & efficiency"    },
    { id: "memory",       name: "MEMORY",       icon: Database,     role: "Episodic & semantic storage"         },
]

const ACTIVITY_CONFIG: Record<AgentActivityStatus, { label: string; color: string; bg: string; border: string }> = {
    active:     { label: "Active",     color: "#4a8c70", bg: "rgba(74,140,112,0.08)",   border: "rgba(74,140,112,0.25)"   },
    processing: { label: "Processing", color: "#82c0a4", bg: "rgba(130,192,164,0.08)",  border: "rgba(130,192,164,0.25)"  },
    done:       { label: "Done",       color: "#4a8c70", bg: "rgba(74,140,112,0.08)",   border: "rgba(74,140,112,0.2)"    },
    idle:       { label: "Idle",       color: "#a3a3a3", bg: "rgba(148,163,184,0.06)", border: "rgba(148,163,184,0.18)" },
    error:      { label: "Error",      color: "#dc2626", bg: "rgba(220,38,38,0.08)",   border: "rgba(220,38,38,0.25)"   },
}

// Agent icon accent color by id
const AGENT_ACCENT: Record<string, string> = {
    orchestrator: "#82c0a4",
    planner:      "#4a8c70",
    research:     "#4a8c70",
    critic:       "#f9a825",
    optimizer:    "#96cead",
    memory:       "#38bdf8",
}

// ==========================================
// MOCK MISSION QUEUE (static)
// ==========================================

const MOCK_MISSIONS = [
    { id: "m1", title: "Research AGI safety frameworks",        status: "running",   priority: "HIGH"   },
    { id: "m2", title: "Analyze distributed system design",     status: "queued",    priority: "MEDIUM" },
    { id: "m3", title: "Generate performance optimization plan",status: "completed", priority: "LOW"    },
]

const MISSION_STATUS = {
    running:   { color: "#82c0a4", label: "Running" },
    queued:    { color: "#f9a825", label: "Queued"  },
    completed: { color: "#4a8c70", label: "Done"    },
    failed:    { color: "#dc2626", label: "Error"   },
}

// ==========================================
// MEMORY LAYERS (static)
// ==========================================

const MEMORY_LAYERS = [
    { label: "Episodic",   value: 847,   max: 1000,  color: "#82c0a4" },
    { label: "Semantic",   value: 1204,  max: 2000,  color: "#4a8c70" },
    { label: "Short-term", value: 12,    max: 50,    color: "#4a8c70" },
    { label: "Vector",     value: 5632,  max: 10000, color: "#96cead" },
]

// ==========================================
// COLLAPSIBLE SECTION
// ==========================================

function Section({
    title, icon: Icon, color = "#82c0a4", children, defaultOpen = true,
    badge,
}: {
    title: string; icon: React.ElementType; color?: string; children: React.ReactNode
    defaultOpen?: boolean; badge?: string
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
                    <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color }}>
                        {title}
                    </span>
                    {badge && (
                        <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full"
                            style={{ background: `${color}15`, color }}>
                            {badge}
                        </span>
                    )}
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
// AGENT CARD
// ==========================================

function AgentCard({
    id, name, icon: Icon, role, status, lastAction,
}: {
    id: string; name: string; icon: React.ElementType
    role: string; status: AgentActivityStatus; lastAction?: string
}) {
    const cfg    = ACTIVITY_CONFIG[status] ?? ACTIVITY_CONFIG.idle
    const accent = AGENT_ACCENT[id] ?? "#82c0a4"
    const isLive = status === "active" || status === "processing"

    return (
        <motion.div
            layout
            className="group flex items-start gap-2 p-2 rounded-lg cursor-default"
            style={{ background: "#f0f7f4", border: `1px solid ${isLive ? cfg.border : "#dceee4"}` }}
            animate={isLive ? { borderColor: cfg.border } : { borderColor: "#dceee4" }}
            transition={{ duration: 0.3 }}
        >
            {/* Icon block */}
            <div
                className="flex items-center justify-center w-6 h-6 mt-0.5 shrink-0 rounded"
                style={{
                    background: `${accent}14`,
                    border:     `1px solid ${accent}28`,
                }}
            >
                <Icon size={10} style={{ color: accent }} />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1 mb-0.5">
                    <div className="flex items-center gap-1.5">
                        {/* Live pulse dot */}
                        <motion.div
                            className="w-1.5 h-1.5 rounded-full shrink-0"
                            style={{ background: cfg.color }}
                            animate={isLive
                                ? { scale: [1, 1.6, 1], opacity: [1, 0.5, 1] }
                                : { scale: 1, opacity: 0.5 }
                            }
                            transition={isLive
                                ? { duration: 1.2, repeat: Infinity }
                                : {}
                            }
                        />
                        <span className="text-xs font-bold text-[#1a1a1a] tracking-tight">{name}</span>
                    </div>
                    <span
                        className="text-[7px] px-1.5 py-0.5 rounded-full shrink-0 font-bold"
                        style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}
                    >
                        {cfg.label}
                    </span>
                </div>

                {/* Last action or default role */}
                <AnimatePresence mode="wait">
                    {isLive && lastAction ? (
                        <motion.p
                            key="action"
                            className="text-xs leading-tight truncate"
                            style={{ color: accent }}
                            initial={{ opacity: 0, y: 3 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        >
                            {lastAction}
                        </motion.p>
                    ) : (
                        <motion.p
                            key="role"
                            className="text-xs text-[#737373] leading-tight truncate"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                        >
                            {role}
                        </motion.p>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    )
}

// ==========================================
// LEFT PANEL
// ==========================================

export default function LeftPanel() {
    const agentActivity  = useRuntimeStore((s) => s.agentActivity)
    const agentLastAction = useRuntimeStore((s) => s.agentLastAction)
    const totalEvents    = useRuntimeStore((s) => s.totalEvents)
    const missionStage   = useMissionStore((s) => s.stage)
    const missionGoal    = useMissionStore((s) => s.goal)
    const startMission   = useMissionStore((s) => s.startMission)
    const resetMission   = useMissionStore((s) => s.resetMission)

    const activeCount = Object.values(agentActivity).filter((s) => s === "active" || s === "processing").length

    return (
        <div
            className="h-full flex flex-col cortex-scroll overflow-y-auto bg-white"
            style={{ borderRight: "1px solid #e8f5ee" }}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-3" style={{ borderBottom: "1px solid #e8f5ee" }}>
                <span className="text-[10px] font-black tracking-widest text-[#82c0a4] uppercase">Systems</span>
                <div className="flex items-center gap-1.5">
                    <motion.div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: "#4a8c70" }}
                        animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }}
                        transition={{ duration: 1.8, repeat: Infinity }}
                    />
                    <span className="text-[9px] text-[#4a8c70] font-semibold">Live</span>
                </div>
            </div>

            {/* -- AGENT SYSTEMS -- */}
            <Section
                title="Agent Systems"
                icon={Network}
                color="#82c0a4"
                badge={activeCount > 0 ? `${activeCount} active` : undefined}
            >
                <div className="flex flex-col gap-1 px-1">
                    {AGENTS.map(({ id, name, icon, role }) => (
                        <AgentCard
                            key={id}
                            id={id}
                            name={name}
                            icon={icon}
                            role={role}
                            status={agentActivity[id] ?? "idle"}
                            lastAction={agentLastAction[id]}
                        />
                    ))}
                </div>
            </Section>

            {/* -- MISSION QUEUE -- */}
            <Section title="Mission Queue" icon={Layers} color="#4a8c70">
                {/* Active mission from store */}
                {missionGoal && missionStage !== "idle" && (
                    <div className="px-2 mb-2">
                        <div className="p-2 rounded-lg" style={{ background: "rgba(130,192,164,0.04)", border: "1px solid rgba(130,192,164,0.2)" }}>
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-[8px] font-bold text-[#82c0a4]">
                                    {missionStage === "completed" ? "DONE" : "LIVE"}
                                </span>
                                <span className="text-[8px] text-[#dc2626]">HIGH</span>
                            </div>
                            <div className="text-[10px] text-[#4a4a4a] leading-tight line-clamp-2">{missionGoal}</div>
                        </div>
                    </div>
                )}
                <div className="flex flex-col gap-1 px-2">
                    {MOCK_MISSIONS.map(({ id, title, status, priority }) => {
                        const cfg = MISSION_STATUS[status as keyof typeof MISSION_STATUS]
                        return (
                            <div key={id} className="p-2 rounded-lg" style={{ background: "#f0f7f4", border: "1px solid #dceee4" }}>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-[8px] px-1 py-0.5 font-bold"
                                        style={{ background: `${cfg.color}10`, border: `1px solid ${cfg.color}30`, color: cfg.color }}>
                                        {cfg.label}
                                    </span>
                                    <span className="text-[8px]"
                                        style={{ color: priority === "HIGH" ? "#dc2626" : priority === "MEDIUM" ? "#f9a825" : "#a3a3a3" }}>
                                        {priority}
                                    </span>
                                </div>
                                <div className="text-[10px] text-[#737373] leading-tight">{title}</div>
                            </div>
                        )
                    })}
                </div>
            </Section>

            {/* -- MEMORY RUNTIME -- */}
            <Section title="Memory Runtime" icon={MemoryStick} color="#4a8c70">
                <div className="flex flex-col gap-2.5 px-2">
                    {MEMORY_LAYERS.map(({ label, value, max, color }) => (
                        <div key={label}>
                            <div className="flex justify-between mb-1">
                                <span className="text-[9px] text-[#a3a3a3]">{label}</span>
                                <span className="text-[9px] font-bold" style={{ color }}>
                                    {value.toLocaleString()}
                                </span>
                            </div>
                            <div className="h-1 rounded-full overflow-hidden bg-[#dceee4]">
                                <motion.div
                                    className="h-full rounded-full"
                                    style={{ background: color }}
                                    initial={{ width: 0 }}
                                    animate={{ width: `${(value / max) * 100}%` }}
                                    transition={{ duration: 0.8, delay: 0.2 }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </Section>

            {/* -- ORCHESTRATION -- */}
            <Section title="Orchestration" icon={Database} color="#82c0a4" defaultOpen={false}>
                <div className="flex flex-col gap-1.5 px-2">
                    {[
                        {
                            icon: Play, label: "Launch Mission", color: "#4a8c70",
                            onClick: () => startMission("Autonomous research and synthesis mission"),
                        },
                        {
                            icon: Square, label: "Stop Runtime", color: "#dc2626",
                            onClick: resetMission,
                        },
                        {
                            icon: RefreshCw, label: "Reset State", color: "#f9a825",
                            onClick: resetMission,
                        },
                    ].map(({ icon: Icon, label, color, onClick }) => (
                        <button
                            key={label}
                            onClick={onClick}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all hover:scale-[1.01]"
                            style={{ background: "#ffffff", border: "1px solid #dceee4", color }}
                        >
                            <Icon size={10} />
                            <span className="text-[9px] font-semibold">{label}</span>
                        </button>
                    ))}
                </div>
            </Section>

            {/* Event counter */}
            <div className="mt-auto px-3 py-2.5 flex items-center justify-between" style={{ borderTop: "1px solid #e8f5ee" }}>
                <span className="text-[8px] text-[#a3a3a3]">Total Events</span>
                <motion.span
                    key={totalEvents}
                    className="text-[9px] font-black text-[#82c0a4] font-mono"
                    initial={{ scale: 1.3, color: "#4a8c70" }}
                    animate={{ scale: 1, color: "#82c0a4" }}
                    transition={{ duration: 0.4 }}
                >
                    {totalEvents.toLocaleString()}
                </motion.span>
            </div>
        </div>
    )
}