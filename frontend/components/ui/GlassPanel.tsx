"use client"
import { cn } from "@/utils/cn"

// ==========================================
// GLASS PANEL
// ==========================================

interface GlassPanelProps {
    children: React.ReactNode
    className?: string
    padding?: boolean
}

export default function GlassPanel({ children, className, padding = true }: GlassPanelProps) {
    return (
        <div
            className={cn(
                "rounded-xl border border-[#dceee4] bg-white",
                "shadow-sm",
                padding && "p-5",
                className
            )}
        >
            {children}
        </div>
    )
}
