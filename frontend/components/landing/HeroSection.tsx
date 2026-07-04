"use client"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, ChevronDown, Activity, Cpu, Database, Zap } from "lucide-react"
import NeuralCore from "./NeuralCore"

// ==========================================
// LIVE STATS
// ==========================================

const STATS = [
    { label: "System Uptime",       value: "99.97%",  icon: Activity },
    { label: "Active Agents",        value: "07",       icon: Cpu      },
    { label: "Missions Executed",    value: "12,847",   icon: Zap      },
    { label: "Memory Sync",          value: "48.2 GB",  icon: Database },
]

// ==========================================
// HERO SECTION — Premium Light
// ==========================================

export default function HeroSection() {
    return (
        <section
            className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden"
            style={{ paddingTop: "5rem", background: "#f0f7f4" }}
        >
            {/* ── Subtle dot grid ── */}
            <div className="absolute inset-0 hex-dot-bg opacity-60 pointer-events-none" />

            {/* ── Soft radial gradient ── */}
            <div className="absolute inset-0 pointer-events-none">
                <div
                    className="absolute"
                    style={{
                        top: "-10%", left: "50%", transform: "translateX(-50%)",
                        width: "80vw", height: "80vw",
                        background: "radial-gradient(ellipse, rgba(130,192,164,0.07) 0%, transparent 60%)",
                    }}
                />
                <div
                    className="absolute"
                    style={{
                        bottom: 0, left: 0, right: 0, height: "30%",
                        background: "linear-gradient(to top, #f0f7f4 0%, transparent 100%)",
                    }}
                />
            </div>

            {/* ── Main content ── */}
            <div className="relative z-10 flex flex-col lg:flex-row items-center gap-12 lg:gap-16 px-8 max-w-7xl w-full mx-auto">

                {/* LEFT: Text */}
                <div className="flex-1 flex flex-col gap-7 text-center lg:text-left">

                    {/* Classification badge */}
                    <motion.div
                        className="flex items-center justify-center lg:justify-start gap-3"
                        initial={{ opacity: 0, x: -24 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.65, delay: 0.1 }}
                    >
                        <div
                            className="flex items-center gap-2 px-3 py-1.5 text-[10px] glyph-mono font-bold tracking-widest rounded-full"
                            style={{
                                background: "rgba(74,140,112,0.08)",
                                border: "1px solid rgba(74,140,112,0.25)",
                                color: "#4a8c70",
                            }}
                        >
                            <span className="w-1.5 h-1.5 rounded-full bg-[#4a8c70] animate-blink" />
                            OPERATIONAL — CLEARANCE LEVEL 5
                        </div>
                    </motion.div>

                    {/* Title */}
                    <motion.div
                        initial={{ opacity: 0, y: 32 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 1.0, delay: 0.22, ease: [0.16, 1, 0.3, 1] }}
                    >
                        <h1 className="font-black leading-none tracking-tight">
                            <span
                                className="block text-[#1a1a1a]"
                                style={{ fontSize: "clamp(3rem, 8.5vw, 7rem)" }}
                            >
                                REALTIME
                            </span>
                            <span
                                className="block text-gradient-blue animate-holo-flicker"
                                style={{ fontSize: "clamp(2rem, 5.5vw, 4.5rem)" }}
                            >
                                AUTONOMOUS
                            </span>
                            <span
                                className="block font-bold"
                                style={{
                                    fontSize: "clamp(0.9rem, 2.4vw, 2rem)",
                                    color: "#4a4a4a",
                                    letterSpacing: "0.12em",
                                }}
                            >
                                COGNITIVE INFRASTRUCTURE
                            </span>
                        </h1>
                    </motion.div>

                    {/* Subheadline */}
                    <motion.p
                        className="text-base lg:text-lg leading-relaxed max-w-lg font-medium"
                        style={{ color: "#4a4a4a" }}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.7, delay: 0.5 }}
                    >
                        An elite multi-agent AI operating system designed for autonomous reasoning,
                        orchestration, and realtime cognition at scale.
                    </motion.p>

                    {/* CTAs */}
                    <motion.div
                        className="flex flex-col sm:flex-row gap-3 items-center lg:items-start"
                        initial={{ opacity: 0, y: 14 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.65 }}
                    >
                        <Link href="/command">
                            <motion.button
                                className="group flex items-center gap-2.5 px-7 py-3.5 text-sm font-semibold text-white rounded-lg"
                                style={{
                                    background: "linear-gradient(135deg, #82c0a4, #4a8c70)",
                                    boxShadow: "0 6px 20px rgba(130,192,164,0.35)",
                                }}
                                whileHover={{ boxShadow: "0 8px 28px rgba(130,192,164,0.45)", y: -1 }}
                                whileTap={{ scale: 0.97 }}
                            >
                                Enter Runtime
                                <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform duration-200" />
                            </motion.button>
                        </Link>

                        <a href="#architecture">
                            <motion.button
                                className="flex items-center gap-2 px-7 py-3.5 text-sm font-semibold text-[#1a1a1a] rounded-lg bg-white"
                                style={{ border: "1.5px solid #dceee4", boxShadow: "0 2px 8px rgba(15,23,42,0.06)" }}
                                whileHover={{ borderColor: "rgba(130,192,164,0.35)", boxShadow: "0 4px 14px rgba(15,23,42,0.1)" }}
                                whileTap={{ scale: 0.97 }}
                            >
                                View Architecture
                            </motion.button>
                        </a>
                    </motion.div>
                </div>

                {/* RIGHT: Neural Core */}
                <motion.div
                    className="shrink-0"
                    initial={{ opacity: 0, scale: 0.6, rotate: -8 }}
                    animate={{ opacity: 1, scale: 1, rotate: 0 }}
                    transition={{ duration: 1.4, delay: 0.28, ease: [0.16, 1, 0.3, 1] }}
                >
                    <NeuralCore size={440} />
                </motion.div>
            </div>

            {/* ── Stats strip ── */}
            <motion.div
                className="relative z-10 w-full max-w-4xl mx-auto px-8 mt-14 lg:mt-10"
                initial={{ opacity: 0, y: 22 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.88 }}
            >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {STATS.map(({ label, value, icon: Icon }) => (
                        <div
                            key={label}
                            className="flex flex-col items-center gap-2 py-5 px-4 rounded-xl bg-white"
                            style={{ border: "1px solid #dceee4", boxShadow: "0 2px 8px rgba(15,23,42,0.05)" }}
                        >
                            <Icon size={16} style={{ color: "#82c0a4" }} />
                            <div className="font-black text-3xl text-[#1a1a1a] tabular-nums leading-none">{value}</div>
                            <div className="text-sm font-semibold text-[#737373] text-center">{label}</div>
                        </div>
                    ))}
                </div>
            </motion.div>

            {/* ── Trusted by ── */}
            <motion.div
                className="relative z-10 w-full max-w-4xl mx-auto px-8 mt-12 mb-8"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 1.1 }}
            >
                <div className="text-center">
                    <p className="text-xs font-bold text-[#737373] tracking-widest uppercase mb-6">Trusted By Elite Teams</p>
                    <div className="flex items-center justify-center gap-10 flex-wrap">
                        {["Nexus Dynamics", "Quantum Systems", "Stratum AI", "Aegis Corp", "Nova Intel"].map(name => (
                            <span key={name} className="text-sm font-semibold text-[#d1d1d1] tracking-wide">{name}</span>
                        ))}
                    </div>
                </div>
            </motion.div>

            {/* ── Scroll indicator ── */}
            <motion.div
                className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-1"
                animate={{ y: [0, 6, 0] }}
                transition={{ duration: 2, repeat: Infinity }}
            >
                <ChevronDown size={18} style={{ color: "#a3a3a3" }} />
            </motion.div>
        </section>
    )
}

