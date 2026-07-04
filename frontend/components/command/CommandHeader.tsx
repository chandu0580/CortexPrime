"use client"
import { motion } from "framer-motion"
import { Wifi, WifiOff, Settings, FlaskConical } from "lucide-react"
import { useRuntimeStore } from "@/store/runtimeStore"
import { useAuthStore } from "@/store/authStore"

// ==========================================
// COMMAND HEADER � MISSION CONTROL
// ==========================================

export default function CommandHeader() {
    const { websocketConnected, runtimeStatus, activeAgents, totalEvents, isDemoMode } = useRuntimeStore()
    const user = useAuthStore(s => s.user)

    const initials = user?.user_id
        ? user.user_id.slice(0, 2).toUpperCase()
        : "CP"

    const isLive = websocketConnected

    return (
        <header
            className="shrink-0 flex items-center justify-between px-6"
            style={{
                height: 64,
                background: "#ffffff",
                borderBottom: "1px solid var(--border-default)",
            }}
        >
            {/* -- Left: wordmark + status -- */}
            <div className="flex items-center gap-4">
                <div>
                    <h1 className="text-sm font-semibold text-[#1a1a1a] leading-none tracking-tight">
                        Mission Control
                    </h1>
                    <p className="text-[11px] text-[#a3a3a3] font-medium leading-none mt-0.5">
                        CortexPrime
                    </p>
                </div>

                {/* Divider */}
                <div style={{ width: 1, height: 24, background: "var(--border-default)" }} />

                {/* Connection badge */}
                <div
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
                    style={{
                        background: isLive ? "var(--color-success-muted)" : isDemoMode ? "rgba(217,119,6,0.08)" : "rgba(220,38,38,0.08)",
                        border: `1px solid ${isLive ? "var(--color-success-border)" : isDemoMode ? "rgba(217,119,6,0.22)" : "rgba(220,38,38,0.22)"}`,
                    }}
                >
                    {isLive ? (
                        <motion.div
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: "var(--color-success)" }}
                            animate={{ opacity: [1, 0.35, 1] }}
                            transition={{ duration: 1.8, repeat: Infinity }}
                        />
                    ) : (
                        <div className="w-1.5 h-1.5 rounded-full" style={{ background: isDemoMode ? "var(--color-warning)" : "var(--color-error)" }} />
                    )}
                    <span
                        className="text-[11px] font-semibold"
                        style={{ color: isLive ? "var(--color-success)" : isDemoMode ? "var(--color-warning)" : "var(--color-error)" }}
                    >
                        {isLive ? "Live" : isDemoMode ? "Demo" : "Offline"}
                    </span>
                </div>

                {/* Active agent count � only when non-zero */}
                {activeAgents > 0 && (
                    <span className="hidden md:block text-[11px] font-medium text-[#737373]">
                        {activeAgents} agent{activeAgents !== 1 ? "s" : ""} active
                    </span>
                )}

                {/* Total events */}
                {totalEvents > 0 && (
                    <span className="hidden lg:block text-[11px] font-medium text-[#a3a3a3]">
                        {totalEvents.toLocaleString()} events
                    </span>
                )}
            </div>

            {/* -- Right: actions + avatar -- */}
            <div className="flex items-center gap-2">
                <button
                    className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150"
                    style={{ color: "#a3a3a3" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "#f0f7f4"; (e.currentTarget as HTMLElement).style.color = "#4a4a4a" }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; (e.currentTarget as HTMLElement).style.color = "#a3a3a3" }}
                    title="Settings"
                    onClick={() => window.location.href = "/settings"}
                >
                    <Settings size={15} />
                </button>

                <div
                    className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold text-white cursor-default select-none"
                    style={{ background: "var(--accent)" }}
                    title={user?.user_id ?? "User"}
                >
                    {initials}
                </div>
            </div>
        </header>
    )
}
