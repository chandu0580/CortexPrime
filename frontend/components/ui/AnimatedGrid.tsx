"use client"
import { cn } from "@/utils/cn"

// ==========================================
// ANIMATED GRID BACKGROUND
// ==========================================

interface AnimatedGridProps {
    className?: string
}

export default function AnimatedGrid({ className }: AnimatedGridProps) {
    return (
        <div
            className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
            aria-hidden
        >
            <svg
                className="absolute inset-0 h-full w-full opacity-[0.4]"
                xmlns="http://www.w3.org/2000/svg"
            >
                <defs>
                    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#dceee4" strokeWidth="0.5" />
                    </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>
        </div>
    )
}
