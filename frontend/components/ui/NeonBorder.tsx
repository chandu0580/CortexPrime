"use client"
import { cn } from "@/utils/cn"

// ==========================================
// NEON BORDER
// ==========================================

interface NeonBorderProps {
    children: React.ReactNode
    className?: string
    active?: boolean
}

export default function NeonBorder({ children, className, active = false }: NeonBorderProps) {
    return (
        <div
            className={cn(
                "relative rounded-xl overflow-hidden",
                active && "animate-glow-breath",
                className
            )}
        >
            <div
                className={cn(
                    "absolute inset-0 rounded-xl pointer-events-none",
                    "bg-gradient-to-br from-[#82c0a4]/20 via-[#96cead]/10 to-[#4a8c70]/20",
                    "opacity-0 transition-opacity duration-300",
                    active && "opacity-100"
                )}
            />
            {children}
        </div>
    )
}
