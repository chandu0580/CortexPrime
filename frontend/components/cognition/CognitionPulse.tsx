"use client"
import { useMemo } from "react"
import { motion } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { useRuntimeStore } from "@/store/runtimeStore"
import { cn } from "@/utils/cn"

// ==========================================
// AGENT IDENTITY � position in neural ring
// ==========================================

const RING_AGENTS = [
    { id: "orchestrator", label: "Orchestrator", color: "#82c0a4", angle: 270 },
    { id: "planner",      label: "Planner",      color: "#4a8c70", angle: 330 },
    { id: "research",     label: "Research",     color: "#4a8c70", angle: 30  },
    { id: "critic",       label: "Critic",       color: "#f9a825", angle: 90  },
    { id: "optimizer",    label: "Optimizer",    color: "#96cead", angle: 150 },
    { id: "memory",       label: "Memory",       color: "#737373", angle: 210 },
]

const deg = (angle: number) => (angle * Math.PI) / 180

// ==========================================
// NEURAL CORE � LIVING AI BRAIN
// ==========================================

interface NeuralCoreProps {
    size?:      number
    className?: string
    showLabels?: boolean
}

export default function NeuralCore({ size = 260, className, showLabels = true }: NeuralCoreProps) {
    const agentActivity = useRuntimeStore((s) => s.agentActivity)
    const isStreaming   = useCognitionStore((s) => s.isStreaming)

    const cx = size / 2
    const cy = size / 2
    const outerR = size * 0.38
    const innerR = size * 0.12

    // Whether the overall system is "alive"
    const anyActive = Object.values(agentActivity).some(
        (s) => s === "active" || s === "processing"
    )

    // Build node positions
    const nodes = useMemo(() =>
        RING_AGENTS.map((a) => ({
            ...a,
            x: cx + outerR * Math.cos(deg(a.angle)),
            y: cy + outerR * Math.sin(deg(a.angle)),
            isActive: agentActivity[a.id] === "active" || agentActivity[a.id] === "processing",
        })),
        [agentActivity, cx, cy, outerR]
    )

    return (
        <div className={cn("flex flex-col items-center gap-3", className)}>
            <svg
                width={size}
                height={size}
                viewBox={`0 0 ${size} ${size}`}
                style={{ overflow: "visible" }}
                aria-label="Neural Core � live agent topology"
            >
                {/* -- Outer ring -- */}
                <circle
                    cx={cx} cy={cy} r={outerR}
                    fill="none"
                    stroke={anyActive ? "rgba(130,192,164,0.15)" : "rgba(226,232,240,0.8)"}
                    strokeWidth={1}
                    style={{ transition: "stroke 0.4s ease" }}
                />

                {/* -- Inner ring -- */}
                <circle
                    cx={cx} cy={cy} r={innerR}
                    fill={anyActive ? "rgba(130,192,164,0.06)" : "rgba(241,245,249,0.8)"}
                    stroke={anyActive ? "rgba(130,192,164,0.25)" : "#dceee4"}
                    strokeWidth={1}
                    style={{ transition: "fill 0.4s ease, stroke 0.4s ease" }}
                />

                {/* -- Central core icon -- */}
                {anyActive ? (
                    <motion.circle
                        cx={cx} cy={cy} r={innerR * 0.55}
                        fill="rgba(130,192,164,0.18)"
                        animate={{ r: [innerR * 0.45, innerR * 0.65, innerR * 0.45] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                    />
                ) : (
                    <circle cx={cx} cy={cy} r={innerR * 0.5} fill="#e8f5ee" />
                )}
                <text
                    x={cx} y={cy + 1}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={size * 0.055}
                    fontWeight={700}
                    fill={anyActive ? "#82c0a4" : "#a3a3a3"}
                    style={{ userSelect: "none", transition: "fill 0.4s ease" }}
                >
                    {isStreaming ? "?" : "?"}
                </text>

                {/* -- Edges: each agent to center -- */}
                {nodes.map((n) => (
                    <line
                        key={`edge-${n.id}`}
                        x1={n.x} y1={n.y}
                        x2={cx}  y2={cy}
                        stroke={n.isActive ? n.color : "#dceee4"}
                        strokeWidth={n.isActive ? 1.5 : 1}
                        strokeDasharray={n.isActive ? "0" : "3 3"}
                        opacity={n.isActive ? 0.7 : 0.4}
                        style={{ transition: "stroke 0.3s ease, stroke-width 0.3s ease, opacity 0.3s ease" }}
                    />
                ))}

                {/* -- Edges: adjacent agents on ring -- */}
                {nodes.map((n, i) => {
                    const next = nodes[(i + 1) % nodes.length]
                    const bothActive = n.isActive && next.isActive
                    return (
                        <line
                            key={`ring-${n.id}`}
                            x1={n.x} y1={n.y}
                            x2={next.x} y2={next.y}
                            stroke={bothActive ? n.color : "#e8f5ee"}
                            strokeWidth={1}
                            opacity={bothActive ? 0.5 : 0.6}
                            style={{ transition: "stroke 0.3s ease" }}
                        />
                    )
                })}

                {/* -- Agent nodes -- */}
                {nodes.map((n) => (
                    <g key={`node-${n.id}`}>
                        {/* Glow ring when active */}
                        {n.isActive && (
                            <motion.circle
                                cx={n.x} cy={n.y} r={size * 0.042}
                                fill="none"
                                stroke={n.color}
                                strokeWidth={1}
                                opacity={0.3}
                                animate={{ r: [size * 0.038, size * 0.055, size * 0.038], opacity: [0.4, 0.15, 0.4] }}
                                transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                            />
                        )}

                        {/* Node circle */}
                        <circle
                            cx={n.x} cy={n.y}
                            r={size * 0.033}
                            fill={n.isActive ? n.color : "#ffffff"}
                            stroke={n.isActive ? n.color : "#dceee4"}
                            strokeWidth={1.5}
                            style={{ transition: "fill 0.25s ease, stroke 0.25s ease" }}
                        />

                        {/* Initial letter */}
                        <text
                            x={n.x} y={n.y + 0.5}
                            textAnchor="middle"
                            dominantBaseline="middle"
                            fontSize={size * 0.032}
                            fontWeight={700}
                            fill={n.isActive ? "#ffffff" : "#a3a3a3"}
                            style={{ userSelect: "none", transition: "fill 0.25s ease" }}
                        >
                            {n.label[0]}
                        </text>

                        {/* Label */}
                        {showLabels && (
                            <text
                                x={n.x + (n.x - cx) * 0.28}
                                y={n.y + (n.y - cy) * 0.28 + 1}
                                textAnchor="middle"
                                dominantBaseline="middle"
                                fontSize={size * 0.038}
                                fontWeight={n.isActive ? 600 : 400}
                                fill={n.isActive ? "#4a4a4a" : "#a3a3a3"}
                                style={{ userSelect: "none", transition: "fill 0.25s ease, font-weight 0.25s ease" }}
                            >
                                {n.label}
                            </text>
                        )}
                    </g>
                ))}
            </svg>

            {/* Status line */}
            <div className="flex items-center gap-2">
                <div
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: anyActive ? "#4a8c70" : "#d1d1d1" }}
                />
                <span className="text-[11px] font-medium text-[#a3a3a3]">
                    {anyActive
                        ? `${Object.values(agentActivity).filter(s => s === "active" || s === "processing").length} agent${Object.values(agentActivity).filter(s => s === "active" || s === "processing").length !== 1 ? "s" : ""} active`
                        : "All agents standby"
                    }
                </span>
            </div>
        </div>
    )
}
