"use client"
import { cn } from "@/utils/cn"

// ==========================================
// RUNTIME GRID
// ==========================================

interface RuntimeGridProps {
    children: React.ReactNode
    cols?: 1 | 2 | 3 | 4
    className?: string
}

const colMap = {
    1: "grid-cols-1",
    2: "grid-cols-1 md:grid-cols-2",
    3: "grid-cols-1 md:grid-cols-2 xl:grid-cols-3",
    4: "grid-cols-1 md:grid-cols-2 xl:grid-cols-4",
}

export default function RuntimeGrid({ children, cols = 3, className }: RuntimeGridProps) {
    return (
        <div className={cn("grid gap-4", colMap[cols], className)}>
            {children}
        </div>
    )
}
