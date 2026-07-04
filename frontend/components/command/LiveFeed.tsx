"use client"
import { useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"

// ==========================================
// AGENT STYLE MAP
// ==========================================

const AGENT_STYLE: Record<string, { text: string; dot: string; bg: string; border: string; tag: string }> = {
    orchestrator: { text: "#82c0a4", dot: "#82c0a4", bg: "rgba(130,192,164,0.05)", border: "rgba(130,192,164,0.15)", tag: "ORCH"   },
    planner:      { text: "#4a8c70", dot: "#4a8c70", bg: "rgba(74,140,112,0.05)",  border: "rgba(74,140,112,0.15)",  tag: "PLAN"   },
    research:     { text: "#4a8c70", dot: "#4a8c70", bg: "rgba(74,140,112,0.05)",  border: "rgba(74,140,112,0.15)",  tag: "RES"    },
    critic:       { text: "#f9a825", dot: "#f9a825", bg: "rgba(217,119,6,0.05)",  border: "rgba(217,119,6,0.15)",  tag: "CRIT"   },
    optimizer:    { text: "#82c0a4", dot: "#96cead", bg: "rgba(130,192,164,0.05)", border: "rgba(130,192,164,0.15)", tag: "OPT"    },
    memory:       { text: "#4a8c70", dot: "#38bdf8", bg: "rgba(74,140,112,0.05)",  border: "rgba(74,140,112,0.15)",  tag: "MEM"    },
    reflection:   { text: "#4a8c70", dot: "#34d399", bg: "rgba(74,140,112,0.05)",  border: "rgba(74,140,112,0.15)",  tag: "REFL"   },
    system:       { text: "#737373", dot: "#a3a3a3", bg: "rgba(100,116,139,0.04)",border: "rgba(100,116,139,0.12)",tag: "SYS"    },
}

const STATUS_DOT: Record<string, string> = {
    success: "#4a8c70",
    info:    "#82c0a4",
    warning: "#f9a825",
    error:   "#dc2626",
}

// ==========================================
// LIVE COGNITION FEED
// ==========================================

export default function LiveFeed({ maxItems = 30 }: { maxItems?: number }) {
    const events    = useCognitionStore((s) => s.events)
    const isStreaming = useCognitionStore((s) => s.isStreaming)
    const scrollRef = useRef<HTMLDivElement>(null)

    // Auto-scroll to top (newest first)
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({ top: 0, behavior: "smooth" })
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [events.length])

    const visible = events.slice(0, maxItems)

    return (
        <div className="flex flex-col h-full">
            {/* Feed header */}
            <div className="flex items-center justify-between px-2 py-1.5 shrink-0">
                <div className="flex items-center gap-1.5">
                    <motion.div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: "#82c0a4" }}
                        animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                        transition={{ duration: 1.8, repeat: Infinity }}
                    />
                    <span className="text-[8px] font-bold tracking-widest text-[#82c0a4] uppercase">
                        Live Stream
                    </span>
                </div>
                <span className="text-[8px] text-[#a3a3a3] font-mono">{events.length} events</span>
            </div>

            {/* Scrollable feed */}
            <div
                ref={scrollRef}
                className="flex-1 flex flex-col gap-1 overflow-y-auto px-1 pb-2"
                style={{ scrollbarWidth: "none" }}
            >
                <AnimatePresence initial={false} mode="popLayout">
                    {visible.map((ev, i) => {
                        const agentKey = ev.agent.toLowerCase()
                        const style    = AGENT_STYLE[agentKey] ?? AGENT_STYLE.system
                        const dot      = STATUS_DOT[ev.status] ?? STATUS_DOT.info
                        const ts = new Date(ev.timestamp).toLocaleTimeString("en", {
                            hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
                        })

                        return (
                            <motion.div
                                key={ev.event_id ?? `${agentKey}-${ev.timestamp}-${i}`}
                                layout
                                initial={{ opacity: 0, y: -10, scale: 0.96 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                                transition={{ duration: 0.22, ease: "easeOut" }}
                                className="flex items-start gap-2 px-2.5 py-2 rounded-lg shrink-0"
                                style={{ background: style.bg, border: `1px solid ${style.border}` }}
                            >
                                {/* Status dot */}
                                <div className="shrink-0 flex flex-col items-center pt-1 gap-1">
                                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: dot }} />
                                </div>

                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5 mb-0.5">
                                        <span
                                            className="text-[8px] font-black uppercase tracking-widest shrink-0 px-1 py-0.5 rounded"
                                            style={{
                                                color:      style.text,
                                                background: `${style.dot}14`,
                                            }}
                                        >
                                            {style.tag}
                                        </span>
                                        <span className="text-[8px] text-[#a3a3a3] font-mono ml-auto shrink-0">
                                            {ts}
                                        </span>
                                    </div>
                                    <p className="text-[10px] text-[#4a4a4a] leading-relaxed line-clamp-2">
                                        {ev.message}
                                    </p>
                                </div>
                            </motion.div>
                        )
                    })}
                </AnimatePresence>

                {/* Empty / Awaiting state */}
                {events.length === 0 && (
                    <div className="flex flex-col items-center gap-2 py-8">
                        <div className="flex gap-1.5">
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    className="w-1.5 h-1.5 rounded-full bg-[#d1d1d1]"
                                    animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
                                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.35 }}
                                />
                            ))}
                        </div>
                        <p className="text-[10px] text-[#a3a3a3]">Awaiting cognitive events…</p>
                    </div>
                )}

                {/* Streaming indicator */}
                {isStreaming && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex items-center gap-2 px-2.5 py-2 rounded-lg shrink-0"
                        style={{ background: "rgba(130,192,164,0.05)", border: "1px solid rgba(130,192,164,0.2)" }}
                    >
                        <div className="flex gap-0.5">
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    className="w-1 h-1 rounded-full"
                                    style={{ background: "#82c0a4" }}
                                    animate={{ scaleY: [1, 2.5, 1] }}
                                    transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.15 }}
                                />
                            ))}
                        </div>
                        <span className="text-[9px] text-[#82c0a4] font-medium">Streaming response…</span>
                    </motion.div>
                )}
            </div>
        </div>
    )
}
