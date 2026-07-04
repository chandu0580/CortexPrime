/**
 * CortexPrime — Executive Command Strip
 *
 * Attaches below the navbar on any page as a global KPI strip.
 * Contains:
 *   - Live system pulse (green/yellow/red)
 *   - Mission command bar (quick-launch input)
 *   - Global KPI row (active missions, agents, events/min, cost today)
 *   - Realtime mission ticker (scrolling feed)
 */
"use client"

import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useCognitionStore } from "@/store/cognitionStore"
import { useRuntimeStore }   from "@/store/runtimeStore"
import { dur, ease, loop, variants } from "@/lib/motion-tokens"
import { PulsingDot, NumberTick } from "@/components/ui/MicroInteractions"

// ─── System pulse indicator ─────────────────────────────────────────────────

function SystemPulse() {
    const agentActivity = useRuntimeStore((s) => s.agentActivity)
    const activeCount   = Object.values(agentActivity).filter((s) => s === "active" || s === "processing").length
    const status = activeCount > 3 ? "critical" : activeCount > 0 ? "active" : "idle"

    const COLOR  = { active: "#4a8c70", idle: "#737373", critical: "#f9a825" }
    const LABEL  = { active: "LIVE",    idle: "STANDBY", critical: "PEAK" }

    return (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <PulsingDot color={COLOR[status]} size={8} />
            <div>
                <p style={{ fontSize: 8, color: "rgba(240,244,255,0.35)", letterSpacing: "0.08em", lineHeight: 1.2 }}>
                    SYSTEM
                </p>
                <p style={{ fontSize: 11, fontWeight: 700, color: COLOR[status], letterSpacing: "0.06em", lineHeight: 1 }}>
                    {LABEL[status]}
                </p>
            </div>
        </div>
    )
}

// ─── KPI strip item ─────────────────────────────────────────────────────────

function KPIItem({ label, value, unit = "", color = "var(--text-primary)" }: {
    label: string; value: number; unit?: string; color?: string
}) {
    return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 60 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
                <NumberTick
                    value={value}
                    style={{ fontSize: 18, fontWeight: 800, color, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}
                />
                {unit && <span style={{ fontSize: 10, color: "rgba(240,244,255,0.4)", fontWeight: 600 }}>{unit}</span>}
            </div>
            <p style={{ fontSize: 9, color: "rgba(240,244,255,0.35)", letterSpacing: "0.07em", textTransform: "uppercase", lineHeight: 1, marginTop: 2 }}>
                {label}
            </p>
        </div>
    )
}

// ─── Mission ticker ─────────────────────────────────────────────────────────

const TICKER_COLORS: Record<string, string> = {
    mission_started:   "#82c0a4",
    mission_completed: "#4a8c70",
    tool_called:       "#4a8c70",
    thinking:          "#96cead",
    error:             "#dc2626",
    default:           "#737373",
}

function MissionTicker() {
    const events = useCognitionStore((s) => s.events)
    const recent = events.slice(-12).reverse()

    return (
        <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
            {/* Fade edges */}
            <div style={{
                position:    "absolute", left: 0, top: 0, bottom: 0, width: 32, zIndex: 2,
                background:  "linear-gradient(to right, var(--surface-raised), transparent)",
                pointerEvents: "none",
            }} />
            <div style={{
                position:    "absolute", right: 0, top: 0, bottom: 0, width: 32, zIndex: 2,
                background:  "linear-gradient(to left, var(--surface-raised), transparent)",
                pointerEvents: "none",
            }} />

            <motion.div
                style={{ display: "flex", alignItems: "center", gap: 24, whiteSpace: "nowrap", paddingLeft: 32 }}
                animate={{ x: [0, -1000] }}
                transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
            >
                {recent.length === 0 ? (
                    <span style={{ fontSize: 10, color: "rgba(240,244,255,0.2)", fontStyle: "italic" }}>
                        Waiting for cognitive events…
                    </span>
                ) : (
                    [...recent, ...recent].map((e, i) => {
                        const color = TICKER_COLORS[e.event_type] ?? TICKER_COLORS.default
                        return (
                            <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                                <span style={{ width: 4, height: 4, borderRadius: "50%", background: color, flexShrink: 0 }} />
                                <span style={{ fontSize: 10, color: "rgba(240,244,255,0.5)", fontWeight: 500 }}>
                                    <span style={{ color, fontWeight: 700 }}>{e.agent}</span>
                                    {" — "}
                                    {e.message?.slice(0, 55)}{(e.message?.length ?? 0) > 55 ? "…" : ""}
                                </span>
                            </span>
                        )
                    })
                )}
            </motion.div>
        </div>
    )
}

// ─── Mission command bar ─────────────────────────────────────────────────────

function MissionCommandBar() {
    const [value, setValue] = useState("")
    const [focused, setFocused] = useState(false)
    const inputRef = useRef<HTMLInputElement>(null)

    // Quick-launch keyboard shortcut
    useEffect(() => {
        function onKey(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault()
                inputRef.current?.focus()
            }
        }
        window.addEventListener("keydown", onKey)
        return () => window.removeEventListener("keydown", onKey)
    }, [])

    return (
        <motion.div
            animate={{
                borderColor: focused ? "rgba(130,192,164,0.6)" : "rgba(255,255,255,0.09)",
                boxShadow:   focused ? "0 0 0 1px rgba(130,192,164,0.3), 0 0 20px rgba(130,192,164,0.1)" : "none",
            }}
            transition={{ duration: dur.fast }}
            style={{
                display:      "flex",
                alignItems:   "center",
                gap:          8,
                padding:      "0 12px",
                borderRadius: 8,
                border:       "1px solid rgba(255,255,255,0.09)",
                background:   "rgba(255,255,255,0.03)",
                height:       32,
                minWidth:     240,
                maxWidth:     320,
            }}
        >
            <span style={{ fontSize: 12, color: "rgba(240,244,255,0.3)", flexShrink: 0 }}>⌘</span>
            <input
                ref={inputRef}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder="Launch mission…"
                style={{
                    flex:        1,
                    background:  "transparent",
                    border:      "none",
                    outline:     "none",
                    fontSize:    11,
                    color:       "var(--text-primary)",
                    fontFamily:  "inherit",
                }}
            />
            {value && (
                <motion.span
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    style={{
                        fontSize:   9,
                        fontWeight: 600,
                        color:      "#82c0a4",
                        border:     "1px solid rgba(130,192,164,0.3)",
                        borderRadius: 4,
                        padding:    "1px 5px",
                        flexShrink: 0,
                        cursor:     "pointer",
                    }}
                    onClick={() => setValue("")}
                >
                    ↵ GO
                </motion.span>
            )}
            {!value && (
                <span style={{ fontSize: 9, color: "rgba(240,244,255,0.2)", flexShrink: 0, border: "1px solid rgba(255,255,255,0.08)", borderRadius: 3, padding: "1px 5px" }}>
                    ⌘K
                </span>
            )}
        </motion.div>
    )
}

// ─── Executive Command Strip ─────────────────────────────────────────────────

export default function ExecutiveCommandStrip() {
    const agentActivity = useRuntimeStore((s) => s.agentActivity)
    const events        = useCognitionStore((s) => s.events)

    const activeAgents   = Object.values(agentActivity).filter((s) => s === "active" || s === "processing").length
    const activeMissions = activeAgents > 0 ? 1 : 0
    const eventsPerMin   = Math.min(events.slice(-60).length, 999)

    return (
        <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: dur.base, ease: ease.out }}
            style={{
                position:     "sticky",
                top:          0,
                zIndex:       40,
                background:   "var(--surface-raised)",
                borderBottom: "1px solid var(--border)",
                padding:      "0 20px",
                height:       52,
                display:      "flex",
                alignItems:   "center",
                gap:          20,
                backdropFilter: "blur(12px)",
            }}
        >
            {/* System pulse */}
            <SystemPulse />

            {/* Divider */}
            <div style={{ width: 1, height: 28, background: "var(--border)" }} />

            {/* KPI strip */}
            <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
                <KPIItem label="missions"  value={activeMissions} color="var(--accent-primary)" />
                <KPIItem label="agents"    value={activeAgents}   color="#4a8c70" />
                <KPIItem label="events/m"  value={eventsPerMin}   color="#96cead" />
            </div>

            {/* Divider */}
            <div style={{ width: 1, height: 28, background: "var(--border)" }} />

            {/* Mission ticker */}
            <MissionTicker />

            {/* Divider */}
            <div style={{ width: 1, height: 28, background: "var(--border)", flexShrink: 0 }} />

            {/* Command bar */}
            <MissionCommandBar />
        </motion.div>
    )
}
