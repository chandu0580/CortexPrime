"use client"
import { motion, AnimatePresence } from "framer-motion"
import { Brain, Zap, Database, CheckCircle, Clock, Activity, ChevronRight } from "lucide-react"
import { useRuntimeStore } from "@/store/runtimeStore"
import { useMissionStore, MISSION_STAGES, STAGE_LABELS } from "@/store/missionStore"
import { useCognitionStore } from "@/store/cognitionStore"
import type { AgentActivityStatus } from "@/store/runtimeStore"

// ==========================================
// AGENT COLOR MAP
// ==========================================

const AGENT_META: Record<string, { label: string; color: string; bg: string; border: string }> = {
    orchestrator: { label: "Orchestrator", color: "#82c0a4", bg: "rgba(130,192,164,0.08)",  border: "rgba(130,192,164,0.2)"  },
    planner:      { label: "Planner",      color: "#4a8c70", bg: "rgba(74,140,112,0.08)",   border: "rgba(74,140,112,0.2)"   },
    research:     { label: "Research",     color: "#4a8c70", bg: "rgba(74,140,112,0.08)",   border: "rgba(74,140,112,0.2)"   },
    critic:       { label: "Critic",       color: "#f9a825", bg: "rgba(217,119,6,0.08)",   border: "rgba(217,119,6,0.2)"   },
    optimizer:    { label: "Optimizer",    color: "#82c0a4", bg: "rgba(130,192,164,0.08)",  border: "rgba(130,192,164,0.2)"  },
}

const STATUS_COLOR: Record<AgentActivityStatus, string> = {
    idle:       "#a3a3a3",
    active:     "#82c0a4",
    processing: "#4a8c70",
    done:       "#4a8c70",
    error:      "#dc2626",
}

const STATUS_LABEL: Record<AgentActivityStatus, string> = {
    idle:       "Idle",
    active:     "Active",
    processing: "Processing",
    done:       "Complete",
    error:      "Error",
}

// ==========================================
// AGENT ROW
// ==========================================

function AgentRow({ agentId, status, lastAction }: { agentId: string; status: AgentActivityStatus; lastAction?: string }) {
    const meta = AGENT_META[agentId.toLowerCase()] ?? {
        label:  agentId.charAt(0).toUpperCase() + agentId.slice(1),
        color:  "#737373",
        bg:     "rgba(100,116,139,0.07)",
        border: "rgba(100,116,139,0.18)",
    }

    const isActive = status === "active" || status === "processing"

    return (
        <motion.div
            layout
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            className="flex items-start gap-3 px-4 py-2.5 rounded-lg"
            style={{ background: meta.bg, border: `1px solid ${meta.border}` }}
        >
            {/* Status dot */}
            <div className="mt-1 shrink-0 relative">
                <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: STATUS_COLOR[status] }}
                />
                {isActive && (
                    <motion.div
                        className="absolute inset-0 rounded-full"
                        style={{ background: STATUS_COLOR[status] }}
                        animate={{ scale: [1, 2.5], opacity: [0.5, 0] }}
                        transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
                    />
                )}
            </div>

            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs font-semibold" style={{ color: meta.color }}>{meta.label}</span>
                    <span className="text-[10px] font-medium" style={{ color: STATUS_COLOR[status] }}>
                        {STATUS_LABEL[status]}
                    </span>
                </div>
                {lastAction && (
                    <p className="text-xs text-[#737373] truncate">{lastAction}</p>
                )}
            </div>
        </motion.div>
    )
}

// ==========================================
// MISSION STAGE TRACKER
// ==========================================

function MissionTracker() {
    const { stage, stageIndex, goal } = useMissionStore()

    if (stage === "idle" || !goal) {
        return (
            <div className="px-4 py-5 flex flex-col items-center justify-center text-center gap-2">
                <div
                    className="flex h-10 w-10 items-center justify-center rounded-xl mb-1"
                    style={{ background: "rgba(130,192,164,0.07)", border: "1px solid rgba(130,192,164,0.15)" }}
                >
                    <Brain size={18} style={{ color: "#82c0a4", opacity: 0.5 }} />
                </div>
                <p className="text-xs font-medium text-[#a3a3a3]">No active mission</p>
                <p className="text-[11px] text-[#b0bec5]">Start a conversation to activate agents</p>
            </div>
        )
    }

    const isComplete = stage === "completed"

    return (
        <div className="px-4 py-3">
            {/* Goal */}
            <p className="text-xs text-[#4a4a4a] font-medium mb-3 truncate" title={goal}>{goal}</p>

            {/* Vertical stage list */}
            <div className="flex flex-col gap-1.5">
                {MISSION_STAGES.map((s, i) => {
                    const isDone    = isComplete || i < stageIndex
                    const isActive  = !isComplete && i === stageIndex

                    return (
                        <div key={s} className="flex items-center gap-2.5">
                            {/* Indicator */}
                            <div className="relative shrink-0 flex items-center justify-center w-4 h-4">
                                {isDone ? (
                                    <CheckCircle size={14} style={{ color: "#4a8c70" }} />
                                ) : isActive ? (
                                    <>
                                        <motion.div
                                            className="w-2 h-2 rounded-full bg-[#82c0a4]"
                                            animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }}
                                            transition={{ duration: 1.2, repeat: Infinity }}
                                        />
                                    </>
                                ) : (
                                    <div className="w-1.5 h-1.5 rounded-full bg-[#d1d1d1]" />
                                )}
                            </div>

                            {/* Label */}
                            <span
                                className="text-xs font-medium"
                                style={{
                                    color: isDone  ? "#4a8c70" :
                                           isActive ? "#82c0a4"  :
                                                      "#a3a3a3",
                                }}
                            >
                                {STAGE_LABELS[s]}
                            </span>

                            {isActive && (
                                <span className="ml-auto text-[10px] font-medium text-[#82c0a4]">Running</span>
                            )}
                            {isDone && (
                                <span className="ml-auto text-[10px] font-medium text-[#4a8c70]">Done</span>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

// ==========================================
// RECENT COGNITION EVENTS
// ==========================================

function RecentEvents() {
    const allEvents = useCognitionStore(s => s.events)
    const events = allEvents.slice(0, 8)

    if (events.length === 0) {
        return (
            <div className="px-4 py-4 text-center">
                <p className="text-[11px] text-[#b0bec5]">Waiting for cognition events...</p>
            </div>
        )
    }

    return (
        <div className="px-3 py-2 flex flex-col gap-1">
            <AnimatePresence initial={false}>
                {events.map((ev, i) => (
                    <motion.div
                        key={ev.event_id ?? i}
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex items-start gap-2 px-2 py-1.5 rounded-md"
                        style={{ background: i === 0 ? "rgba(130,192,164,0.05)" : "transparent" }}
                    >
                        <div
                            className="mt-1 w-1.5 h-1.5 rounded-full shrink-0"
                            style={{
                                background:
                                    ev.type === "success" ? "#4a8c70" :
                                    ev.type === "error"   ? "#dc2626" :
                                    ev.type === "warning" ? "#f9a825" :
                                                            "#82c0a4",
                            }}
                        />
                        <p className="text-[11px] text-[#737373] leading-snug line-clamp-2">{ev.message}</p>
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    )
}

// ==========================================
// RUNTIME STATS
// ==========================================

function RuntimeStats() {
    const { activeAgents, totalEvents, websocketConnected, latency } = useRuntimeStore()

    const stats = [
        { icon: Activity,  label: "Agents",  value: String(activeAgents)          },
        { icon: Zap,       label: "Events",  value: String(totalEvents)            },
        { icon: Clock,     label: "Latency", value: latency || "—"                 },
        { icon: Database,  label: "WS",      value: websocketConnected ? "Live" : "Sim" },
    ]

    return (
        <div className="grid grid-cols-2 gap-1.5 px-4 py-2">
            {stats.map(({ icon: Icon, label, value }) => (
                <div
                    key={label}
                    className="flex items-center gap-2 px-2.5 py-2 rounded-lg"
                    style={{ background: "rgba(248,250,252,1)", border: "1px solid #dceee4" }}
                >
                    <Icon size={12} style={{ color: "#a3a3a3" }} />
                    <div>
                        <p className="text-[10px] text-[#a3a3a3] leading-none mb-0.5">{label}</p>
                        <p className="text-xs font-semibold text-[#4a4a4a]">{value}</p>
                    </div>
                </div>
            ))}
        </div>
    )
}

// ==========================================
// SECTION HEADER
// ==========================================

function SectionHeader({ title, children }: { title: string; children?: React.ReactNode }) {
    return (
        <div
            className="flex items-center justify-between px-4 py-2"
            style={{ borderBottom: "1px solid #e8f5ee" }}
        >
            <span className="text-[10px] font-bold tracking-widest uppercase text-[#a3a3a3]">{title}</span>
            {children}
        </div>
    )
}

// ==========================================
// COGNITION PANEL
// ==========================================

export default function CognitionPanel() {
    const { agentActivity, agentLastAction } = useRuntimeStore()

    const activeAgentEntries = Object.entries(agentActivity).filter(
        ([, status]) => status !== "idle"
    )

    return (
        <div
            className="h-full flex flex-col overflow-hidden bg-white"
            style={{ borderLeft: "1px solid #dceee4" }}
        >
            {/* ── Header ── */}
            <div
                className="shrink-0 flex items-center gap-2.5 px-4 py-3.5"
                style={{ borderBottom: "1px solid #dceee4" }}
            >
                <div
                    className="flex h-7 w-7 items-center justify-center rounded-lg"
                    style={{ background: "rgba(130,192,164,0.08)", border: "1px solid rgba(130,192,164,0.18)" }}
                >
                    <Brain size={14} style={{ color: "#82c0a4" }} />
                </div>
                <div>
                    <h3 className="text-xs font-bold text-[#1a1a1a]">Cognition</h3>
                    <p className="text-[10px] text-[#a3a3a3]">Agent Activity</p>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto cortex-scroll flex flex-col">

                {/* ── System stats ── */}
                <div className="shrink-0">
                    <RuntimeStats />
                </div>

                {/* ── Mission ── */}
                <div className="shrink-0" style={{ borderTop: "1px solid #e8f5ee" }}>
                    <SectionHeader title="Mission" />
                    <MissionTracker />
                </div>

                {/* ── Active agents ── */}
                {activeAgentEntries.length > 0 && (
                    <div className="shrink-0" style={{ borderTop: "1px solid #e8f5ee" }}>
                        <SectionHeader title={`Active Agents · ${activeAgentEntries.length}`} />
                        <div className="px-3 py-2 flex flex-col gap-1.5">
                            <AnimatePresence>
                                {activeAgentEntries.map(([id, status]) => (
                                    <AgentRow
                                        key={id}
                                        agentId={id}
                                        status={status}
                                        lastAction={agentLastAction[id]}
                                    />
                                ))}
                            </AnimatePresence>
                        </div>
                    </div>
                )}

                {/* ── Cognition events ── */}
                <div className="flex-1 min-h-0" style={{ borderTop: "1px solid #e8f5ee" }}>
                    <SectionHeader title="Live Events">
                        <span className="flex items-center gap-1 text-[10px] text-[#82c0a4]">
                            <motion.span
                                className="inline-block w-1 h-1 rounded-full bg-[#82c0a4]"
                                animate={{ opacity: [1, 0.3, 1] }}
                                transition={{ duration: 1.2, repeat: Infinity }}
                            />
                            Live
                        </span>
                    </SectionHeader>
                    <RecentEvents />
                </div>
            </div>
        </div>
    )
}
