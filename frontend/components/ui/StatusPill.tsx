"use client"
import { cn } from "@/utils/cn"

// ==========================================
// STATUS PILL
// ==========================================

interface StatusPillProps {
    label: string
    variant?: "default" | "success" | "warning" | "error" | "info"
    className?: string
}

const variantMap = {
    default: "bg-[#e8f5ee] text-[#4a4a4a]",
    success: "bg-[#f0fdf4] text-[#4a8c70] border border-[#bbf7d0]",
    warning: "bg-[#fffbeb] text-[#f9a825] border border-[#fde68a]",
    error:   "bg-[#fef2f2] text-[#dc2626] border border-[#fecaca]",
    info:    "bg-[#f0f9ff] text-[#4a8c70] border border-[#bae6fd]",
}

export default function StatusPill({ label, variant = "default", className }: StatusPillProps) {
    return (
        <span
            className={cn(
                "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide",
                variantMap[variant],
                className
            )}
        >
            {label}
        </span>
    )
}
