"use client"
import { cn } from "@/utils/cn"

// ==========================================
// RUNTIME BADGE
// ==========================================

interface RuntimeBadgeProps {
    label: string
    status?: "active" | "idle" | "error" | "degraded"
    className?: string
}

const statusMap = {
    active:   "bg-[#f0fdf4] text-[#4a8c70] border-[#bbf7d0]",
    idle:     "bg-[#f0f7f4] text-[#737373] border-[#dceee4]",
    error:    "bg-[#fef2f2] text-[#dc2626] border-[#fecaca]",
    degraded: "bg-[#fffbeb] text-[#f9a825] border-[#fde68a]",
}

export default function RuntimeBadge({ label, status = "idle", className }: RuntimeBadgeProps) {
    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold",
                statusMap[status],
                className
            )}
        >
            <span className={cn(
                "h-1.5 w-1.5 rounded-full",
                status === "active"   && "bg-[#4a8c70] animate-pulse",
                status === "idle"     && "bg-[#a3a3a3]",
                status === "error"    && "bg-[#dc2626]",
                status === "degraded" && "bg-[#f9a825]",
            )} />
            {label}
        </span>
    )
}
