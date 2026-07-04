"use client"
import { motion } from "framer-motion"

// ==========================================
// NEURAL FLOW
// ==========================================

interface NeuralFlowProps {
    width?: number
    height?: number
    className?: string
}

export default function NeuralFlow({ width = 300, height = 80, className }: NeuralFlowProps) {
    const nodes = [
        { cx: 30,  cy: 40 },
        { cx: 110, cy: 20 },
        { cx: 110, cy: 60 },
        { cx: 190, cy: 40 },
        { cx: 270, cy: 20 },
        { cx: 270, cy: 60 },
    ]

    const edges = [
        { x1: 30, y1: 40, x2: 110, y2: 20 },
        { x1: 30, y1: 40, x2: 110, y2: 60 },
        { x1: 110, y1: 20, x2: 190, y2: 40 },
        { x1: 110, y1: 60, x2: 190, y2: 40 },
        { x1: 190, y1: 40, x2: 270, y2: 20 },
        { x1: 190, y1: 40, x2: 270, y2: 60 },
    ]

    return (
        <svg
            className={className}
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
        >
            {edges.map((e, i) => (
                <motion.line
                    key={i}
                    x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                    stroke="#a855f7"
                    strokeWidth={1}
                    strokeDasharray="4 4"
                    animate={{ strokeDashoffset: [8, 0] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.15, ease: "linear" }}
                />
            ))}
            {nodes.map((n, i) => (
                <motion.circle
                    key={i}
                    cx={n.cx} cy={n.cy} r={5}
                    fill="#a855f7"
                    animate={{ opacity: [0.4, 1, 0.4], r: [4, 6, 4] }}
                    transition={{ duration: 2, repeat: Infinity, delay: i * 0.3, ease: "easeInOut" }}
                />
            ))}
        </svg>
    )
}
