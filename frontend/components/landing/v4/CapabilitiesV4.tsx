/**
 * CortexPrime — Interactive Capability Cards V4
 * Upgraded from V3: hover depth tilt, animated glow border, expand on click.
 */
"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { DepthCard, GlowBorder, FadeIn, StaggerList, StaggerItem } from "@/components/ui/MicroInteractions"
import { dur, ease } from "@/lib/motion-tokens"

const CAPABILITIES = [
    {
        icon: "⬡", title: "Multi-Agent Reasoning", color: "#82c0a4", href: "/cognition",
        tag: "Core Intelligence",
        desc: "5 specialized agents collaborate in parallel — Planner, Researcher, Critic, Optimizer, and Orchestrator.",
        bullets: ["Parallel task execution", "Critic validation layer", "Optimizer synthesis", "Real-time coordination"],
        metric: { label: "Agents", value: "5" },
    },
    {
        icon: "◎", title: "Persistent Memory", color: "#4a8c70", href: "/memory-explorer",
        tag: "Always Learning",
        desc: "Episodic, semantic, and vector memory that persists across sessions with automatic reflection and consolidation.",
        bullets: ["ChromaDB vector search", "Cross-session recall", "Semantic consolidation", "Episodic timeline"],
        metric: { label: "Memory Stores", value: "4" },
    },
    {
        icon: "🖥", title: "Computer Control", color: "#a78bfa", href: "/operator",
        tag: "Autonomous",
        desc: "Full desktop and browser automation. CortexPrime can see your screen, click, type, and browse like a human.",
        bullets: ["Playwright browser", "Screenshot + OCR vision", "GUI interaction", "Desktop automation"],
        metric: { label: "Tools", value: "12+" },
    },
    {
        icon: "▶", title: "Mission Replay", color: "#818cf8", href: "/replay",
        tag: "Auditability",
        desc: "Step-by-step playback of any completed mission. Review every agent decision, action, and thought.",
        bullets: ["Timeline visualization", "Agent state replay", "Decision audit", "Governance review"],
        metric: { label: "Traceable", value: "100%" },
    },
    {
        icon: "🎙", title: "Voice Interface", color: "#f59e0b", href: "/voice",
        tag: "Live",
        desc: "Natural voice interaction with wake-word detection, Whisper transcription, and real-time TTS synthesis.",
        bullets: ["Wake-word detection", "Whisper STT 97%+", "Natural TTS", "Real-time conversation"],
        metric: { label: "Latency", value: "<200ms" },
    },
    {
        icon: "◇", title: "Safety & Governance", color: "#f87171", href: "/governance-center",
        tag: "Always On",
        desc: "Real-time guardrails, human approval queues, and a complete audit trail for every AI decision.",
        bullets: ["Prompt injection guard", "Human approval queue", "Compliance scoring", "Full audit trail"],
        metric: { label: "Coverage", value: "100%" },
    },
]

function CapabilityCard({ cap, index }: { cap: typeof CAPABILITIES[0]; index: number }) {
    const [expanded, setExpanded] = useState(false)

    return (
        <StaggerItem>
            <DepthCard maxTilt={5} depth={12}>
                <GlowBorder color={`${cap.color}55`} radius={14}>
                    <motion.div
                        onClick={() => setExpanded(!expanded)}
                        style={{
                            background:   "var(--surface)",
                            borderRadius: 14,
                            padding:      "22px 22px 18px",
                            cursor:       "pointer",
                            position:     "relative",
                            overflow:     "hidden",
                        }}
                        animate={{ minHeight: expanded ? 240 : 160 }}
                        transition={{ duration: dur.medium, ease: ease.out }}
                    >
                        {/* Corner accent */}
                        <div style={{
                            position:     "absolute",
                            top:          0,
                            right:        0,
                            width:        80,
                            height:       80,
                            background:   `radial-gradient(circle at top right, ${cap.color}14, transparent 70%)`,
                            pointerEvents:"none",
                        }} />

                        {/* Header */}
                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <motion.div
                                    whileHover={{ scale: 1.15, rotate: 5 }}
                                    transition={{ duration: dur.fast, ease: ease.back }}
                                    style={{
                                        width:          38,
                                        height:         38,
                                        borderRadius:   10,
                                        background:     `${cap.color}18`,
                                        border:         `1px solid ${cap.color}35`,
                                        display:        "flex",
                                        alignItems:     "center",
                                        justifyContent: "center",
                                        fontSize:       17,
                                        flexShrink:     0,
                                    }}
                                >
                                    {cap.icon}
                                </motion.div>
                                <div>
                                    <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.2 }}>
                                        {cap.title}
                                    </p>
                                    <span style={{
                                        fontSize:     9,
                                        fontWeight:   700,
                                        color:        cap.color,
                                        letterSpacing:"0.07em",
                                        textTransform:"uppercase",
                                    }}>
                                        {cap.tag}
                                    </span>
                                </div>
                            </div>

                            {/* Metric badge */}
                            <div style={{
                                textAlign:    "right",
                                flexShrink:   0,
                                borderLeft:   `2px solid ${cap.color}40`,
                                paddingLeft:  10,
                                marginLeft:   8,
                            }}>
                                <p style={{ fontSize: 16, fontWeight: 800, color: cap.color, lineHeight: 1 }}>
                                    {cap.metric.value}
                                </p>
                                <p style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
                                    {cap.metric.label}
                                </p>
                            </div>
                        </div>

                        {/* Description */}
                        <p style={{ fontSize: 11.5, color: "var(--text-secondary)", lineHeight: 1.55, marginBottom: expanded ? 14 : 0 }}>
                            {cap.desc}
                        </p>

                        {/* Expanded bullets */}
                        <AnimatePresence>
                            {expanded && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: "auto" }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: dur.medium, ease: ease.out }}
                                    style={{ overflow: "hidden" }}
                                >
                                    <div style={{ borderTop: `1px solid var(--border)`, paddingTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                                        {cap.bullets.map((b) => (
                                            <div key={b} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                                <div style={{ width: 3, height: 3, borderRadius: "50%", background: cap.color, flexShrink: 0 }} />
                                                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{b}</span>
                                            </div>
                                        ))}
                                    </div>
                                    <Link
                                        href={cap.href}
                                        style={{
                                            display:      "inline-flex",
                                            alignItems:   "center",
                                            gap:          4,
                                            marginTop:    12,
                                            fontSize:     11,
                                            fontWeight:   600,
                                            color:        cap.color,
                                            textDecoration:"none",
                                        }}
                                        onClick={(e) => e.stopPropagation()}
                                    >
                                        Explore →
                                    </Link>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Expand hint */}
                        {!expanded && (
                            <div style={{ position: "absolute", bottom: 12, right: 14 }}>
                                <span style={{ fontSize: 9, color: "rgba(240,244,255,0.2)" }}>click to expand</span>
                            </div>
                        )}
                    </motion.div>
                </GlowBorder>
            </DepthCard>
        </StaggerItem>
    )
}

export default function CapabilitiesV4() {
    return (
        <section style={{ padding: "100px 24px", maxWidth: 1200, margin: "0 auto" }}>
            <FadeIn direction="up">
                <div style={{ textAlign: "center", marginBottom: 60 }}>
                    <span style={{
                        display:      "inline-block",
                        fontSize:     11,
                        fontWeight:   700,
                        letterSpacing:"0.12em",
                        textTransform:"uppercase",
                        color:        "var(--accent-primary)",
                        marginBottom: 14,
                    }}>
                        Platform Capabilities
                    </span>
                    <h2 className="type-heading-xl" style={{ marginBottom: 16 }}>
                        Everything You Need.
                    </h2>
                    <p style={{ fontSize: 16, color: "var(--text-secondary)", maxWidth: 520, margin: "0 auto" }}>
                        Six enterprise-grade systems working in concert. Click any card to explore.
                    </p>
                </div>
            </FadeIn>

            <StaggerList staggerDelay={0.08} childDelay={0.1}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 20 }}>
                    {CAPABILITIES.map((cap, i) => (
                        <CapabilityCard key={cap.title} cap={cap} index={i} />
                    ))}
                </div>
            </StaggerList>
        </section>
    )
}
