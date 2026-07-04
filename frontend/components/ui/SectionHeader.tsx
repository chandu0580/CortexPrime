"use client"
import { cn } from "@/utils/cn"

// ==========================================
// SECTION HEADER
// ==========================================

interface SectionHeaderProps {
    title: string
    subtitle?: string
    action?: React.ReactNode
    className?: string
    accent?: boolean
}

export default function SectionHeader({ title, subtitle, action, className, accent }: SectionHeaderProps) {
    return (
        <div className={cn("flex items-start justify-between gap-4 mb-4", className)}>
            <div>
                <h2
                    className={cn(
                        "text-xl font-bold tracking-tight text-[#1a1a1a]",
                        accent && "bg-gradient-to-r from-[#82c0a4] to-[#4a8c70] bg-clip-text text-transparent"
                    )}
                >
                    {title}
                </h2>
                {subtitle && (
                    <p className="mt-0.5 text-sm font-medium text-[#737373]">{subtitle}</p>
                )}
            </div>
            {action && <div className="shrink-0">{action}</div>}
        </div>
    )
}
