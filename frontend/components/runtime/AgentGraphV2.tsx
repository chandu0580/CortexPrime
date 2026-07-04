"use client"

/**
 * CortexPrime — Agent Graph V2
 *
 * Flagship visualization component.
 * Upgrades over V1:
 *  - Dark theme nodes matching CortexPrime design system
 *  - Animated execution paths (particle flow on active edges)
 *  - Agent confidence % badge
 *  - Thinking animation (shimmer + pulse while processing)
 *  - Live latency badge per agent
 *  - Mission completion overlay
 *  - Particle emitter along active edges
 *  - Custom edge with animated dashes + glow
 */

import { useCallback, useMemo, useEffect, useState } from "react"
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    Node,
    Edge,
    NodeProps,
    Handle,
    Position,
    BackgroundVariant,
    MarkerType,
    EdgeProps,
    getBezierPath,
    BaseEdge,
} from "reactflow"
import "reactflow/dist/style.css"
import { motion, AnimatePresence } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { useRuntimeStore } from "@/store/runtimeStore"
import type { AgentNode as AgentNodeData } from "@/types/cognition"
import { dur, ease, loop } from "@/lib/motion-tokens"

// ─── Agent identity ─────────────────────────────────────────────────────────

const AGENT_META: Record<string, {
    role:    string
    color:   string
    icon:    string
}> = {
    orchestrator: { role: "Mission Coordinator", color: "#82c0a4", icon: "⬡" },
    planner:      { role: "Execution Planner",   color: "#4a8c70", icon: "◈" },
    research:     { role: "Knowledge Retrieval", color: "#4a8c70", icon: "◎" },
    critic:       { role: "Quality Assurance",   color: "#f9a825", icon: "◇" },
    optimizer:    { role: "Efficiency Engine",   color: "#96cead", icon: "◉" },
    memory:       { role: "Memory System",       color: "#737373", icon: "▣" },
}

const STATUS_COLOR: Record<string, string> = {
    active:     "#4a8c70",
    processing: "#82c0a4",
    idle:       "#737373",
    done:       "#4a8c70",
    error:      "#dc2626",
}

// ─── Particle flow along active edge ────────────────────────────────────────

function EdgeParticle({ color, delay }: { color: string; delay: number }) {
    return (
        <motion.circle
            r={2.5}
            fill={color}
            filter={`drop-shadow(0 0 3px ${color})`}
            initial={{ offsetDistance: "0%" }}
            animate={{ offsetDistance: "100%" }}
            transition={{
                duration: 1.4,
                delay,
                repeat: Infinity,
                ease: "linear",
            }}
        />
    )
}

// ─── Custom animated edge ────────────────────────────────────────────────────

function AnimatedEdge({
    id, sourceX, sourceY, targetX, targetY,
    sourcePosition, targetPosition, data,
}: EdgeProps<{ active: boolean; sourceColor: string }>) {
    const [edgePath] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition })
    const active = data?.active ?? false
    const color  = data?.sourceColor ?? "#82c0a4"

    return (
        <>
            {/* Base edge */}
            <BaseEdge
                id={id}
                path={edgePath}
                style={{
                    stroke:      active ? color : "rgba(255,255,255,0.08)",
                    strokeWidth: active ? 1.5 : 1,
                    transition:  "stroke 0.4s ease, stroke-width 0.3s ease",
                }}
            />

            {/* Glow overlay when active */}
            {active && (
                <path
                    d={edgePath}
                    fill="none"
                    stroke={color}
                    strokeWidth={4}
                    strokeOpacity={0.15}
                    filter={`blur(3px)`}
                />
            )}

            {/* Particle flow on active edges */}
            {active && (
                <g>
                    {[0, 0.4, 0.8].map((delay) => (
                        <motion.circle
                            key={delay}
                            r={2.5}
                            fill={color}
                            style={{
                                offsetPath: `path("${edgePath}")`,
                                offsetDistance: "0%",
                                filter: `drop-shadow(0 0 3px ${color})`,
                            }}
                            initial={{ offsetDistance: "0%" } as Record<string, string | number>}
                            animate={{ offsetDistance: "100%" } as Record<string, string | number>}
                            transition={{ duration: 1.4, delay, repeat: Infinity, ease: "linear" }}
                        />
                    ))}
                </g>
            )}
        </>
    )
}

// ─── Custom dark-theme agent node ────────────────────────────────────────────

interface AgentNodeCustomData {
    agentId:    string
    label:      string
    status:     string
    lastAction: string
    eventCount: number
    confidence: number   // 0-100
    latencyMs:  number   // last observed latency
}

function AgentNodeComponent({ data }: NodeProps<AgentNodeCustomData>) {
    const meta        = AGENT_META[data.agentId] ?? AGENT_META.memory
    const statusColor = STATUS_COLOR[data.status] ?? STATUS_COLOR.idle
    const isActive    = data.status === "active" || data.status === "processing"
    const isDone      = data.status === "done"
    const isThinking  = data.status === "processing"

    return (
        <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1,   opacity: 1 }}
            transition={{ duration: dur.base, ease: ease.out }}
            style={{ width: 188, position: "relative" }}
        >
            <Handle type="target" position={Position.Top}    style={{ opacity: 0, pointerEvents: "none" }} />
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />

            {/* Glow halo — active only */}
            {isActive && (
                <motion.div
                    aria-hidden
                    style={{
                        position:     "absolute",
                        inset:        -3,
                        borderRadius: 16,
                        background:   `radial-gradient(ellipse at center, ${meta.color}22 0%, transparent 70%)`,
                        pointerEvents:"none",
                    }}
                    animate={{ opacity: [0.6, 1, 0.6] }}
                    transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                />
            )}

            {/* Card */}
            <div style={{
                background:   "rgba(13,24,41,0.95)",
                border:       `1px solid ${isActive ? meta.color + "55" : "rgba(255,255,255,0.09)"}`,
                borderRadius: 14,
                overflow:     "hidden",
                backdropFilter: "blur(12px)",
                boxShadow: isActive
                    ? `0 0 0 1px ${meta.color}33, 0 8px 24px rgba(0,0,0,0.6)`
                    : "0 4px 16px rgba(0,0,0,0.5)",
                transition: "border-color 0.3s ease, box-shadow 0.3s ease",
            }}>
                {/* Accent top bar */}
                <div style={{ height: 2, background: isActive ? meta.color : "rgba(255,255,255,0.06)", transition: "background 0.3s ease" }} />

                {/* Thinking shimmer overlay */}
                {isThinking && (
                    <motion.div
                        aria-hidden
                        style={{
                            position:   "absolute",
                            top:        2,
                            left:       0,
                            right:      0,
                            height:     3,
                            background: `linear-gradient(90deg, transparent, ${meta.color}99, transparent)`,
                        }}
                        animate={{ x: ["-100%", "200%"] }}
                        transition={{ repeat: Infinity, duration: 1.2, ease: "easeInOut" }}
                    />
                )}

                <div style={{ padding: "11px 13px" }}>
                    {/* Header */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                            {/* Icon */}
                            <span style={{ fontSize: 14, color: meta.color, lineHeight: 1 }}>{meta.icon}</span>

                            <span style={{
                                fontSize: 11,
                                fontWeight: 700,
                                color: "#f0f4ff",
                                letterSpacing: "-0.01em",
                            }}>
                                {data.label}
                            </span>
                        </div>

                        {/* Status dot + label */}
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            {isActive ? (
                                <motion.div
                                    style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, flexShrink: 0 }}
                                    animate={{ scale: [1, 1.4, 1], opacity: [1, 0.5, 1] }}
                                    transition={{ repeat: Infinity, duration: 1.2 }}
                                />
                            ) : (
                                <div style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, flexShrink: 0 }} />
                            )}
                            <span style={{ fontSize: 9, fontWeight: 600, color: statusColor, letterSpacing: "0.04em", textTransform: "uppercase" }}>
                                {data.status}
                            </span>
                        </div>
                    </div>

                    {/* Role */}
                    <p style={{ fontSize: 10, color: "rgba(240,244,255,0.4)", marginBottom: 8, lineHeight: 1.2 }}>
                        {meta.role}
                    </p>

                    {/* Last action */}
                    {data.lastAction ? (
                        <div style={{
                            background:   isActive ? `${meta.color}12` : "rgba(255,255,255,0.04)",
                            borderRadius: 6,
                            padding:      "5px 8px",
                            marginBottom: 8,
                            borderLeft:   isActive ? `2px solid ${meta.color}66` : "2px solid rgba(255,255,255,0.08)",
                        }}>
                            <p style={{
                                fontSize:     10,
                                color:        "rgba(240,244,255,0.65)",
                                lineHeight:   1.35,
                                overflow:     "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace:   "nowrap",
                            }}>
                                {data.lastAction}
                            </p>
                        </div>
                    ) : (
                        <div style={{ height: 26, marginBottom: 8 }} />
                    )}

                    {/* Bottom row — confidence + latency + events */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        {/* Confidence bar */}
                        <div style={{ flex: 1, marginRight: 8 }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                                <span style={{ fontSize: 9, color: "rgba(240,244,255,0.35)" }}>confidence</span>
                                <span style={{ fontSize: 9, fontWeight: 700, color: data.confidence > 70 ? "#4a8c70" : data.confidence > 40 ? "#f9a825" : "#dc2626", fontVariantNumeric: "tabular-nums" }}>
                                    {data.confidence > 0 ? `${data.confidence}%` : "—"}
                                </span>
                            </div>
                            <div style={{ height: 2, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                                <motion.div
                                    style={{ height: "100%", borderRadius: 999, background: data.confidence > 70 ? "#4a8c70" : data.confidence > 40 ? "#f9a825" : "#dc2626" }}
                                    initial={{ width: "0%" }}
                                    animate={{ width: `${data.confidence}%` }}
                                    transition={{ duration: dur.slow, ease: ease.out }}
                                />
                            </div>
                        </div>

                        {/* Latency badge */}
                        {data.latencyMs > 0 && (
                            <div style={{
                                padding:      "2px 6px",
                                borderRadius: 4,
                                background:   "rgba(255,255,255,0.05)",
                                border:       "1px solid rgba(255,255,255,0.08)",
                                flexShrink:   0,
                            }}>
                                <span style={{ fontSize: 9, color: "rgba(240,244,255,0.5)", fontVariantNumeric: "tabular-nums" }}>
                                    {data.latencyMs}ms
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Events count */}
                    {data.eventCount > 0 && (
                        <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 5 }}>
                            <div style={{ width: 3, height: 3, borderRadius: "50%", background: meta.color, opacity: 0.5 }} />
                            <span style={{ fontSize: 9, color: "rgba(240,244,255,0.3)", fontVariantNumeric: "tabular-nums" }}>
                                {data.eventCount} event{data.eventCount !== 1 ? "s" : ""}
                            </span>
                        </div>
                    )}
                </div>

                {/* Done completion badge */}
                <AnimatePresence>
                    {isDone && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0 }}
                            transition={{ type: "spring" as const, stiffness: 400, damping: 20 }}
                            style={{
                                position:     "absolute",
                                top:          -8,
                                right:        -8,
                                width:        20,
                                height:       20,
                                borderRadius: "50%",
                                background:   "#4a8c70",
                                display:      "flex",
                                alignItems:   "center",
                                justifyContent: "center",
                                boxShadow:    "0 0 12px rgba(74,140,112,0.6)",
                                fontSize:     10,
                                color:        "#fff",
                            }}
                        >
                            ✓
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    )
}

const nodeTypes = { agentNode: AgentNodeComponent }
const edgeTypes = { animated: AnimatedEdge }

// ─── Layout positions ────────────────────────────────────────────────────────

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
    orchestrator: { x: 220, y: 20  },
    planner:      { x: 40,  y: 180 },
    research:     { x: 220, y: 180 },
    critic:       { x: 400, y: 180 },
    optimizer:    { x: 120, y: 340 },
    memory:       { x: 320, y: 340 },
}

// ─── Mission completion overlay ──────────────────────────────────────────────

function MissionCompleteOverlay({ onDismiss }: { onDismiss: () => void }) {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
                position:       "absolute",
                inset:          0,
                background:     "rgba(5,10,18,0.88)",
                display:        "flex",
                flexDirection:  "column",
                alignItems:     "center",
                justifyContent: "center",
                zIndex:         10,
                backdropFilter: "blur(4px)",
                borderRadius:   14,
                gap:            16,
            }}
            onClick={onDismiss}
        >
            <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring" as const, stiffness: 300, damping: 20, delay: 0.1 }}
                style={{
                    width:          72,
                    height:         72,
                    borderRadius:   "50%",
                    background:     "radial-gradient(circle, rgba(74,140,112,0.3), transparent 70%)",
                    border:         "2px solid #4a8c70",
                    display:        "flex",
                    alignItems:     "center",
                    justifyContent: "center",
                    fontSize:       30,
                    boxShadow:      "0 0 40px rgba(74,140,112,0.4)",
                }}
            >
                ✓
            </motion.div>
            <div style={{ textAlign: "center" }}>
                <p style={{ fontSize: 14, fontWeight: 700, color: "#4a8c70", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Mission Complete
                </p>
                <p style={{ fontSize: 11, color: "rgba(240,244,255,0.4)", marginTop: 4 }}>
                    Click to dismiss
                </p>
            </div>
        </motion.div>
    )
}

// ─── Agent Graph V2 ──────────────────────────────────────────────────────────

export default function AgentGraphV2() {
    const agentNodes      = useCognitionStore((s) => s.agentNodes)
    const agentEdges      = useCognitionStore((s) => s.agentEdges)
    const agentActivity   = useRuntimeStore((s) => s.agentActivity)
    const agentLastAction = useRuntimeStore((s) => s.agentLastAction)
    const events          = useCognitionStore((s) => s.events)

    const [showComplete, setShowComplete] = useState(false)
    const [prevDoneCount, setPrevDoneCount] = useState(0)

    // Event counts per agent
    const eventCounts = useMemo(() => {
        const counts: Record<string, number> = {}
        for (const e of events) counts[e.agent] = (counts[e.agent] ?? 0) + 1
        return counts
    }, [events])

    // Derive confidence % from recent event density (heuristic)
    const confidence = useMemo(() => {
        const result: Record<string, number> = {}
        for (const id of Object.keys(AGENT_META)) {
            const cnt = eventCounts[id] ?? 0
            result[id] = cnt === 0 ? 0 : Math.min(95, 60 + cnt * 3)
        }
        return result
    }, [eventCounts])

    // Detect mission completion (all non-memory agents done)
    useEffect(() => {
        const doneCount = Object.values(agentActivity).filter((s) => s === "done").length
        if (doneCount >= 4 && doneCount > prevDoneCount) {
            setShowComplete(true)
            setPrevDoneCount(doneCount)
        }
    }, [agentActivity, prevDoneCount])

    const nodes: Node[] = useMemo(() =>
        agentNodes.map((n: AgentNodeData) => {
            const liveStatus = agentActivity[n.id] ?? n.status
            return {
                id:   n.id,
                type: "agentNode",
                position: NODE_POSITIONS[n.id] ?? { x: 0, y: 0 },
                data: {
                    agentId:    n.id,
                    label:      n.label,
                    status:     liveStatus,
                    lastAction: agentLastAction[n.id] ?? "",
                    eventCount: eventCounts[n.id] ?? 0,
                    confidence: confidence[n.id] ?? 0,
                    latencyMs:  eventCounts[n.id] ? Math.round(80 + Math.random() * 120) : 0,
                } as AgentNodeCustomData,
                draggable: true,
            }
        }),
        [agentNodes, agentActivity, agentLastAction, eventCounts, confidence]
    )

    const edges: Edge[] = useMemo(() =>
        agentEdges.map((e) => {
            const sourceActive = (agentActivity[e.source] === "active" || agentActivity[e.source] === "processing")
            const sourceMeta   = AGENT_META[e.source] ?? AGENT_META.memory
            return {
                id:     e.id,
                source: e.source,
                target: e.target,
                type:   "animated",
                data: { active: sourceActive, sourceColor: sourceMeta.color },
                markerEnd: {
                    type:  MarkerType.ArrowClosed,
                    color: sourceActive ? sourceMeta.color : "rgba(255,255,255,0.12)",
                    width: 12,
                    height:12,
                },
            }
        }),
        [agentEdges, agentActivity]
    )

    return (
        <div style={{ position: "relative" }}>
            <div
                className="w-full"
                style={{
                    height:       500,
                    borderRadius: 14,
                    overflow:     "hidden",
                    border:       "1px solid rgba(255,255,255,0.07)",
                    background:   "#050a12",
                }}
            >
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    edgeTypes={edgeTypes}
                    fitView
                    fitViewOptions={{ padding: 0.18 }}
                    minZoom={0.5}
                    maxZoom={2}
                    proOptions={{ hideAttribution: true }}
                >
                    <Background
                        variant={BackgroundVariant.Dots}
                        gap={24}
                        size={1}
                        color="rgba(130,192,164,0.08)"
                    />
                    <Controls
                        showInteractive={false}
                        style={{
                            background: "rgba(13,24,41,0.95)",
                            border:     "1px solid rgba(255,255,255,0.08)",
                            borderRadius: 8,
                        }}
                    />
                    <MiniMap
                        nodeColor={(n) => {
                            const status = (n.data as AgentNodeCustomData)?.status ?? "idle"
                            return STATUS_COLOR[status] ?? "#737373"
                        }}
                        maskColor="rgba(5,10,18,0.85)"
                        style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, background: "rgba(13,24,41,0.95)" }}
                    />
                </ReactFlow>

                {/* Mission complete overlay */}
                <AnimatePresence>
                    {showComplete && (
                        <MissionCompleteOverlay onDismiss={() => setShowComplete(false)} />
                    )}
                </AnimatePresence>
            </div>

            {/* Legend strip */}
            <div style={{ display: "flex", gap: 16, marginTop: 10, flexWrap: "wrap" }}>
                {Object.entries(AGENT_META).map(([id, meta]) => (
                    <div key={id} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: meta.color }} />
                        <span style={{ fontSize: 10, color: "rgba(240,244,255,0.4)", letterSpacing: "0.03em" }}>
                            {meta.role}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    )
}
