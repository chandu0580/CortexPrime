"use client"
import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Zap, CheckCircle, Clock, Radio, Terminal } from "lucide-react"

// ==========================================
// COGNITION EVENT FEED
// ==========================================

const EVENTS = [
    { agent: "ORCHESTRATOR", msg: "Initializing mission tree — autonomous research mode",   color: "#82c0a4", type: "init"    },
    { agent: "PLANNER",      msg: "Decomposing objective into 4 executable sub-tasks",        color: "#4a8c70", type: "plan"    },
    { agent: "PLANNER",      msg: "Priority matrix computed — critical path identified",       color: "#4a8c70", type: "plan"    },
    { agent: "RESEARCHER",   msg: "Executing web search: 'AGI safety alignment 2026'",        color: "#4a8c70", type: "search"  },
    { agent: "RESEARCHER",   msg: "Analyzing 18 sources — synthesizing key frameworks",       color: "#4a8c70", type: "search"  },
    { agent: "RESEARCHER",   msg: "Constitutional AI + RLHF alignment identified as primary", color: "#4a8c70", type: "result"  },
    { agent: "CRITIC",       msg: "Validating research quality — coherence score: 96%",       color: "#82c0a4", type: "eval"    },
    { agent: "CRITIC",       msg: "Response approved — no hallucination detected",            color: "#82c0a4", type: "pass"    },
    { agent: "OPTIMIZER",    msg: "Refining output structure for maximum clarity",             color: "#4a8c70", type: "refine"  },
    { agent: "MEMORY",       msg: "Synchronized — 6 episodic records written to store",       color: "#4a8c70", type: "memory"  },
    { agent: "REFLECTION",   msg: "Performance insight logged — routing improved by 12%",     color: "#82c0a4", type: "reflect" },
    { agent: "ORCHESTRATOR", msg: "Mission complete — full report stored in semantic memory", color: "#4a8c70", type: "done"    },
]

const TYPE_ICON: Record<string, React.ElementType> = {
    init:    Zap,
    plan:    Terminal,
    search:  Terminal,
    result:  CheckCircle,
    eval:    Clock,
    pass:    CheckCircle,
    refine:  Terminal,
    memory:  Terminal,
    reflect: Terminal,
    done:    CheckCircle,
}

// ==========================================
// STREAMING TEXT
// ==========================================

function StreamText({ text, onDone }: { text: string; onDone: () => void }) {
    const [displayed, setDisplayed] = useState("")

    useEffect(() => {
        setDisplayed("")
        let i = 0
        const id = setInterval(() => {
            i++
            setDisplayed(text.slice(0, i))
            if (i >= text.length) {
                clearInterval(id)
                setTimeout(onDone, 340)
            }
        }, 22)
        return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [text])

    return (
        <span>
            {displayed}
            {displayed.length < text.length && (
                <span className="animate-stream-cursor ml-px">▌</span>
            )}
        </span>
    )
}

// ==========================================
// LIVE COGNITION SECTION
// ==========================================

export default function LiveCognitionSection() {
    const [visibleCount, setVisibleCount] = useState(0)
    const [streamingIdx, setStreamingIdx] = useState(0)
    const [running, setRunning] = useState(false)

    // Auto-start once in view
    function startCycle() {
        if (running) return
        setRunning(true)
        setVisibleCount(0)
        setStreamingIdx(0)
    }

    function handleEventDone() {
        setVisibleCount(v => {
            const next = v + 1
            if (next < EVENTS.length) {
                setStreamingIdx(next)
            } else {
                // restart after pause
                setTimeout(() => {
                    setVisibleCount(0)
                    setStreamingIdx(0)
                }, 2200)
            }
            return next
        })
    }

    return (
        <section id="cognition" className="relative py-28 px-8 overflow-hidden" style={{ background: "#f0f7f4" }}>
            <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(130,192,164,0.18), transparent)" }} />

            <div className="max-w-6xl mx-auto">

                {/* Header */}
                <motion.div
                    className="mb-12"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                    onViewportEnter={startCycle}
                >
                    <div className="text-[10px] glyph-mono tracking-widest text-[#82c0a4] mb-3 font-semibold uppercase">
                        ── Live Cognition Preview ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl text-[#1a1a1a]">
                        Cognition <span className="text-gradient-blue">In Motion</span>
                    </h2>
                    <p className="mt-4 text-sm text-[#737373] max-w-xl leading-relaxed">
                        Watch the cognitive process unfold in real time — every agent thought,
                        decision, and action streamed live.
                    </p>
                </motion.div>

                {/* Terminal panel */}
                <motion.div
                    className="relative"
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.15 }}
                    viewport={{ once: true }}
                    style={{ border: "1px solid #dceee4", borderRadius: "1rem", overflow: "hidden", boxShadow: "0 8px 24px rgba(15,23,42,0.08)" }}
                >
                    {/* Terminal header bar */}
                    <div
                        className="flex items-center justify-between px-5 py-3"
                        style={{ background: "#f0f7f4", borderBottom: "1px solid #dceee4" }}
                    >
                        <div className="flex items-center gap-3">
                            {/* Traffic lights */}
                            <div className="flex gap-1.5">
                                {["#ef4444", "#f59e0b", "#82c0a4"].map(c => (
                                    <div key={c} className="w-2.5 h-2.5 rounded-full" style={{ background: c, opacity: 0.55 }} />
                                ))}
                            </div>
                            <Terminal size={11} className="text-[#a3a3a3]" />
                            <span className="glyph-mono text-[10px] tracking-widest text-[#737373]">
                                CORTEXPRIME — LIVE COGNITION STREAM
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Radio size={10} className="text-[#82c0a4]" />
                            <motion.span
                                className="glyph-mono text-[9px] text-[#82c0a4]"
                                animate={{ opacity: [1, 0.4, 1] }}
                                transition={{ duration: 1.4, repeat: Infinity }}
                            >
                                LIVE
                            </motion.span>
                        </div>
                    </div>

                    {/* Event feed */}
                    <div
                        className="relative p-5 flex flex-col gap-2 overflow-hidden"
                        style={{ background: "#ffffff", minHeight: 400 }}
                    >
                        {/* Scan line overlay */}
                        <motion.div
                            className="absolute left-0 right-0 h-px pointer-events-none"
                            style={{
                                background: "linear-gradient(90deg, transparent, rgba(14,165,233,0.25), transparent)",
                                zIndex: 10,
                            }}
                            animate={{ top: ["0%", "100%"] }}
                            transition={{ duration: 3.5, repeat: Infinity, ease: "linear" }}
                        />

                        <AnimatePresence mode="popLayout">
                            {EVENTS.slice(0, visibleCount + 1).map((evt, idx) => {
                                const Icon = TYPE_ICON[evt.type] ?? Terminal
                                const isStreaming = idx === streamingIdx && running
                                const isDone = idx < streamingIdx || (!running && idx <= visibleCount)
                                return (
                                    <motion.div
                                        key={`${idx}-${visibleCount}`}
                                        initial={{ opacity: 0, x: -12 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0 }}
                                        transition={{ duration: 0.25 }}
                                        className="flex items-start gap-3 px-3 py-2.5 rounded-lg"
                                        style={{
                                            background: isStreaming ? "rgba(130,192,164,0.05)" : "transparent",
                                            borderLeft: isStreaming ? `2px solid ${evt.color}` : "2px solid transparent",
                                        }}
                                    >
                                        {/* Icon */}
                                        <Icon
                                            size={12}
                                            className="mt-0.5 shrink-0"
                                            style={{ color: evt.color }}
                                        />

                                        {/* Agent label */}
                                        <span
                                            className="glyph-mono text-[9px] font-bold tracking-widest shrink-0"
                                            style={{ color: evt.color, minWidth: 90 }}
                                        >
                                            {evt.agent}
                                        </span>

                                        {/* Message */}
                                        <span className="text-xs" style={{ color: isDone ? "#4a4a4a" : "#737373" }}>
                                            {isStreaming ? (
                                                <StreamText text={evt.msg} onDone={handleEventDone} />
                                            ) : (
                                                evt.msg
                                            )}
                                        </span>

                                        {/* Done check */}
                                        {isDone && (
                                            <CheckCircle size={10} className="ml-auto shrink-0 mt-0.5" style={{ color: "#1e3a2f" }} />
                                        )}
                                    </motion.div>
                                )
                            })}
                        </AnimatePresence>

                        {/* Idle placeholder rows */}
                        {!running && (
                            <div className="flex flex-col gap-2 opacity-30">
                                {[...Array(5)].map((_, i) => (
                                    <div
                                        key={i}
                                        className="h-6 rounded-sm"
                                        style={{
                                            background: "rgba(14,165,233,0.04)",
                                            width: `${55 + i * 8}%`,
                                        }}
                                    />
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Input bar */}
                    <div
                        className="flex items-center gap-3 px-5 py-3"
                        style={{ background: "#06060f", borderTop: "1px solid rgba(14,165,233,0.1)" }}
                    >
                        <Zap size={12} className="text-[#82c0a4]" />
                        <div className="flex-1 glyph-mono text-xs text-[#1e293b]">
                            Mission directive active — streaming cognitive events...
                        </div>
                        <motion.div
                            className="w-1.5 h-1.5 rounded-full bg-[#82c0a4]"
                            animate={{ opacity: [1, 0.2, 1] }}
                            transition={{ duration: 0.9, repeat: Infinity }}
                        />
                    </div>
                </motion.div>
            </div>
        </section>
    )
}
