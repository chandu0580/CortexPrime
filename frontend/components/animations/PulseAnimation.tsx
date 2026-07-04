"use client"
import { motion } from "framer-motion"
import { cn } from "@/utils/cn"

// ==========================================
// PULSE ANIMATION
// ==========================================

interface PulseAnimationProps {
    size?: number
    color?: string
    className?: string
}

export default function PulseAnimation({ size = 12, color = "#a855f7", className }: PulseAnimationProps) {
    return (
        <span className={cn("relative inline-flex", className)} style={{ width: size, height: size }}>
            <motion.span
                className="absolute inset-0 rounded-full"
                style={{ background: color }}
                animate={{ scale: [1, 2.2], opacity: [0.7, 0] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
            />
            <span className="relative rounded-full" style={{ width: size, height: size, background: color }} />
        </span>
    )
}
