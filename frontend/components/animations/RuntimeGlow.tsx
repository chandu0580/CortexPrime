"use client"
import { motion } from "framer-motion"
import { cn } from "@/utils/cn"

// ==========================================
// RUNTIME GLOW
// ==========================================

interface RuntimeGlowProps {
    active?: boolean
    color?: string
    className?: string
    children?: React.ReactNode
}

export default function RuntimeGlow({ active = true, color = "#a855f7", className, children }: RuntimeGlowProps) {
    return (
        <motion.div
            className={cn("relative", className)}
            animate={active ? {
                boxShadow: [
                    `0 0 8px ${color}40`,
                    `0 0 24px ${color}70`,
                    `0 0 8px ${color}40`,
                ],
            } : {}}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
        >
            {children}
        </motion.div>
    )
}
