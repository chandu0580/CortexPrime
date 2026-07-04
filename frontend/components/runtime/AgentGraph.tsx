"use client"

import { useCallback, useMemo } from "react"
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
} from "reactflow"
import "reactflow/dist/style.css"
import { motion, AnimatePresence } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { useRuntimeStore } from "@/store/runtimeStore"
import type { AgentNode as AgentNodeData } from "@/types/cognition"

// ==========================================
// AGENT IDENTITY CONFIG
// ==========================================

const AGENT_META: Record<string, {
    role:    string
    color:   string
    bgMuted: string
    border:  string
}> = {
    orchestrator: {
        role:    "Mission Coordinator",
        color:   "#82c0a4",
        bgMuted: "rgba(130,192,164,0.07)",
        border:  "rgba(130,192,164,0.22)",
    },
    planner: {
        role:    "Execution Planner",
        color:   "#4a8c70",
        bgMuted: "rgba(74,140,112,0.07)",
        border:  "rgba(74,140,112,0.22)",
    },
    research: {
        role:    "Knowledge Retrieval",
        color:   "#4a8c70",
        bgMuted: "rgba(74,140,112,0.07)",
        border:  "rgba(74,140,112,0.22)",
    },
    critic: {
        role:    "Quality Assurance",
        color:   "#f9a825",
        bgMuted: "rgba(217,119,6,0.07)",
        border:  "rgba(217,119,6,0.22)",
    },
    optimizer: {
        role:    "Efficiency Engine",
        color:   "#96cead",
        bgMuted: "rgba(124,58,237,0.07)",
        border:  "rgba(124,58,237,0.22)",
    },
    memory: {
        role:    "Memory System",
        color:   "#737373",
        bgMuted: "rgba(71,85,105,0.07)",
        border:  "rgba(71,85,105,0.22)",
    },
}

// ==========================================
// STATUS INDICATOR
// ==========================================

const STATUS_COLOR: Record<string, string> = {
    active:     "#4a8c70",
    processing: "#82c0a4",
    idle:       "#d1d1d1",
    done:       "#4a8c70",
    error:      "#dc2626",
}

const STATUS_LABEL: Record<string, string> = {
    active:     "Active",
    processing: "Processing",
    idle:       "Standby",
    done:       "Done",
    error:      "Error",
}

// ==========================================
// CUSTOM AGENT NODE
// ==========================================

interface AgentNodeCustomData {
    agentId:    string
    label:      string
    status:     string
    lastAction: string
    eventCount: number
}

function AgentNodeComponent({ data }: NodeProps<AgentNodeCustomData>) {
    const meta = AGENT_META[data.agentId] ?? AGENT_META.memory
    const statusColor = STATUS_COLOR[data.status] ?? STATUS_COLOR.idle
    const statusLabel = STATUS_LABEL[data.status] ?? "Standby"
    const isActive = data.status === "active" || data.status === "processing"

    return (
        <div
            style={{
                width: 200,
                background: "#ffffff",
                border: `1px solid ${isActive ? meta.border : "#dceee4"}`,
                borderRadius: 12,
                boxShadow: isActive
                    ? `0 4px 16px rgba(0,0,0,0.06), 0 0 0 1px ${meta.border}`
                    : "0 1px 4px rgba(0,0,0,0.05)",
                transition: "all 0.25s ease",
                overflow: "hidden",
            }}
        >
            <Handle type="target" position={Position.Top}    style={{ opacity: 0, pointerEvents: "none" }} />
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />

            {/* Color accent bar */}
            <div style={{ height: 3, background: isActive ? meta.color : "#dceee4", transition: "background 0.3s ease" }} />

            <div style={{ padding: "12px 14px" }}>
                {/* Header row */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{
                        fontSize: 12,
                        fontWeight: 700,
                        color: "#1a1a1a",
                        letterSpacing: "-0.01em",
                        lineHeight: 1.2,
                    }}>
                        {data.label}
                    </span>

                    {/* Status indicator */}
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <div style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: statusColor,
                            flexShrink: 0,
                        }} />
                        <span style={{
                            fontSize: 10,
                            fontWeight: 600,
                            color: statusColor,
                            lineHeight: 1,
                        }}>
                            {statusLabel}
                        </span>
                    </div>
                </div>

                {/* Role */}
                <p style={{
                    fontSize: 10,
                    color: "#a3a3a3",
                    fontWeight: 500,
                    lineHeight: 1.3,
                    marginBottom: 8,
                }}>
                    {meta.role}
                </p>

                {/* Last action */}
                {data.lastAction && (
                    <div style={{
                        background: isActive ? meta.bgMuted : "#f0f7f4",
                        borderRadius: 6,
                        padding: "5px 8px",
                        marginBottom: 6,
                    }}>
                        <p style={{
                            fontSize: 10,
                            color: "#737373",
                            lineHeight: 1.4,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            maxWidth: "100%",
                        }}>
                            {data.lastAction}
                        </p>
                    </div>
                )}

                {/* Event count */}
                {data.eventCount > 0 && (
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{
                            fontSize: 10,
                            color: "#a3a3a3",
                            fontVariantNumeric: "tabular-nums",
                        }}>
                            {data.eventCount} event{data.eventCount !== 1 ? "s" : ""}
                        </span>
                    </div>
                )}
            </div>
        </div>
    )
}

const nodeTypes = { agentNode: AgentNodeComponent }

// ==========================================
// LAYOUT POSITIONS
// ==========================================

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
    orchestrator: { x: 220, y: 20  },
    planner:      { x: 40,  y: 180 },
    research:     { x: 220, y: 180 },
    critic:       { x: 400, y: 180 },
    optimizer:    { x: 120, y: 340 },
    memory:       { x: 320, y: 340 },
}

// ==========================================
// AGENT GRAPH (FLAGSHIP)
// ==========================================

export default function AgentGraph() {
    const agentNodes   = useCognitionStore((s) => s.agentNodes)
    const agentEdges   = useCognitionStore((s) => s.agentEdges)
    const agentActivity  = useRuntimeStore((s) => s.agentActivity)
    const agentLastAction = useRuntimeStore((s) => s.agentLastAction)

    // Track per-agent event counts
    const events = useCognitionStore((s) => s.events)
    const eventCounts = useMemo(() => {
        const counts: Record<string, number> = {}
        for (const e of events) {
            counts[e.agent] = (counts[e.agent] ?? 0) + 1
        }
        return counts
    }, [events])

    // Build React Flow nodes from store
    const nodes: Node[] = useMemo(() =>
        agentNodes.map((n: AgentNodeData) => {
            const liveStatus = agentActivity[n.id] ?? n.status
            const pos = NODE_POSITIONS[n.id] ?? { x: 0, y: 0 }
            return {
                id:   n.id,
                type: "agentNode",
                position: pos,
                data: {
                    agentId:    n.id,
                    label:      n.label,
                    status:     liveStatus,
                    lastAction: agentLastAction[n.id] ?? "",
                    eventCount: eventCounts[n.id] ?? 0,
                } as AgentNodeCustomData,
                draggable: true,
            }
        }),
        [agentNodes, agentActivity, agentLastAction, eventCounts]
    )

    // Build React Flow edges with animated status
    const edges: Edge[] = useMemo(() =>
        agentEdges.map((e) => {
            const sourceActive = (agentActivity[e.source] === "active")
            return {
                id:       e.id,
                source:   e.source,
                target:   e.target,
                animated: sourceActive,
                style: {
                    strokeWidth: 1.5,
                    stroke: sourceActive ? "#82c0a4" : "#dceee4",
                    transition: "stroke 0.3s ease",
                },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: sourceActive ? "#82c0a4" : "#dceee4",
                    width: 14,
                    height: 14,
                },
            }
        }),
        [agentEdges, agentActivity]
    )

    return (
        <div
            className="w-full"
            style={{ height: 500, borderRadius: 14, overflow: "hidden", border: "1px solid #dceee4", background: "#fafbfc" }}
        >
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                minZoom={0.5}
                maxZoom={2}
                proOptions={{ hideAttribution: true }}
            >
                <Background
                    variant={BackgroundVariant.Dots}
                    gap={20}
                    size={1}
                    color="rgba(130,192,164,0.12)"
                />
                <Controls
                    showInteractive={false}
                    style={{
                        background: "#ffffff",
                        border: "1px solid #dceee4",
                        borderRadius: 8,
                        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                    }}
                />
                <MiniMap
                    nodeColor={(n) => {
                        const status = (n.data as AgentNodeCustomData)?.status ?? "idle"
                        return STATUS_COLOR[status] ?? "#d1d1d1"
                    }}
                    maskColor="rgba(248,250,252,0.85)"
                    style={{ border: "1px solid #dceee4", borderRadius: 8 }}
                />
            </ReactFlow>
        </div>
    )
}
