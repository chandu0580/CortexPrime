"use client"
import { useRealtime } from "@/hooks/useRealtime"
import { useRuntimeStore } from "@/store/runtimeStore"
import { useUxStore } from "@/store/uxStore"
import ThemeToggle from "@/components/theme/ThemeToggle"
import { Bell, Command, Search } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"

// ==========================================
// CORTEX NAVBAR
// ==========================================

interface CortexNavbarProps {
    title?:    string
    subtitle?: string
}

export default function CortexNavbar({ title = "CortexPrime", subtitle }: CortexNavbarProps) {
    const { status }                          = useRealtime()
    const { activeAgents, runtimeStatus }     = useRuntimeStore()

    const wsColor = status === "connected"  ? "var(--success)"
                  : status === "connecting" ? "var(--warning)"
                  :                           "var(--danger)"

    return (
        <header
            className="sticky top-0 z-30 flex h-12 items-center justify-between px-6"
            style={{
                background:     "var(--glass-bg)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                borderBottom:   "1px solid var(--border)",
                boxShadow:      "var(--shadow-xs)",
            }}
        >
            {/* Title */}
            <div className="flex items-center gap-3">
                <h1 style={{ fontSize: "var(--font-size-nav)", fontWeight: 700, letterSpacing: "-0.01em", color: "var(--text-primary)" }}>
                    {title}
                </h1>
                {subtitle && (
                    <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 500, color: "var(--text-muted)" }} className="hidden sm:block">
                        {subtitle}
                    </span>
                )}
            </div>

            {/* Status row */}
            <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5" style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: wsColor }}>
                    <span className="w-1.5 h-1.5 rounded-full animate-blink" style={{ background: wsColor }} />
                    {status === "connected" ? "Live" : status.charAt(0).toUpperCase() + status.slice(1)}
                </span>
                <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 500, color: "var(--text-muted)" }} className="hidden sm:block">
                    {activeAgents} Agents
                </span>
                <span
                    style={{
                        fontSize:   "var(--font-size-xs)",
                        fontWeight: 600,
                        color:      runtimeStatus === "healthy" ? "var(--success)" : "var(--warning)",
                    }}
                >
                    {runtimeStatus.charAt(0).toUpperCase() + runtimeStatus.slice(1)}
                </span>

                {/* Command Palette */}
                <button
                    onClick={() => useUxStore.getState().setCommandCenterOpen(true)}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-[8px] border border-[#E8EDF3] text-[0.7rem] font-medium text-[#6B7280] hover:bg-[#F5F7FA] transition-colors"
                    aria-label="Open command palette"
                    title="Ctrl+K"
                >
                    <Command className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Cmd+K</span>
                </button>

                {/* Notification Bell */}
                <button
                    onClick={() => useUxStore.getState().setNotificationCenterOpen(true)}
                    className="relative flex h-8 w-8 items-center justify-center rounded-[8px] text-[#6B7280] hover:bg-[#F5F7FA] transition-colors"
                    aria-label="Open notifications"
                >
                    <Bell className="h-4 w-4" />
                    <UnreadBadge />
                </button>

                <ThemeToggle variant="compact" />
            </div>
        </header>
    )
}

function UnreadBadge() {
    const unreadCount = useUxStore((s) => s.unreadCount)
    if (unreadCount === 0) return null
    return (
        <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#EF4444] px-1 text-[0.55rem] font-bold text-white ring-2 ring-white"
        >
            {unreadCount > 9 ? "9+" : unreadCount}
        </motion.span>
    )
}

