"use client"
import { motion } from "framer-motion"
import { cn } from "@/utils/cn"

// ==========================================
// GLOW CARD
// ==========================================

interface GlowCardProps {
    children: React.ReactNode
    className?: string
    color?: "purple" | "cyan" | "emerald" | "pink"
    onClick?: () => void
}

const colorMap = {
    purple:  "border-[#dceee4] hover:border-[#82c0a4]/30 hover:shadow-[#82c0a4]/5",
    cyan:    "border-[#dceee4] hover:border-[#4a8c70]/30 hover:shadow-[#4a8c70]/5",
    emerald: "border-[#dceee4] hover:border-[#4a8c70]/30 hover:shadow-[#4a8c70]/5",
    pink:    "border-[#dceee4] hover:border-[#dc2626]/20 hover:shadow-[#dc2626]/5",
}

export default function GlowCard({ children, className, color = "purple", onClick }: GlowCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            onClick={onClick}
            className={cn(
                "relative rounded-xl border bg-white p-5",
                "transition-all duration-200 hover:shadow-md",
                colorMap[color],
                onClick && "cursor-pointer",
                className
            )}
        >
            {children}
        </motion.div>
    )
}
