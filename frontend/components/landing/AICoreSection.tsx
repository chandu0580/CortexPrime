"use client"
import { motion } from "framer-motion"
import { Brain, Network, Database, Zap, Eye, Mic, Cpu } from "lucide-react"

// ==========================================
// CORE MODULES
// ==========================================

const MODULES = [
    { icon: Brain,    label: "COGNITION ENGINE", value: "< 120ms",  sub: "Decision latency",   color: "#82c0a4", col: "left" },
    { icon: Network,  label: "AGENT MESH",        value: "7 Agents", sub: "Concurrent ops",     color: "#4a8c70", col: "left" },
    { icon: Database, label: "MEMORY FABRIC",     value: "4-Tier",   sub: "Episodic · Vector",  color: "#4a8c70", col: "left" },
    { icon: Zap,      label: "LLM ROUTER",        value: "4 Providers",sub:"Dynamic routing",   color: "#82c0a4", col: "right"},
    { icon: Eye,      label: "VISION PIPELINE",   value: "Real-time", sub:"OCR · Screenshot",   color: "#4a8c70", col: "right"},
    { icon: Mic,      label: "VOICE INTERFACE",   value: "Wake-word", sub:"STT · TTS",           color: "#4a8c70", col: "right"},
]

const LEFT  = MODULES.filter(m => m.col === "left")
const RIGHT = MODULES.filter(m => m.col === "right")

// ==========================================
// MODULE CARD — Light
// ==========================================

function ModuleCard({ icon: Icon, label, value, sub, color, index, side }: {
    icon: React.ElementType; label: string; value: string; sub: string; color: string; index: number; side: "left" | "right"
}) {
    return (
        <motion.div
            className="relative group flex items-center gap-3 px-4 py-3 bg-white rounded-xl cursor-default"
            style={{ border: "1px solid #dceee4", boxShadow: "0 2px 8px rgba(15,23,42,0.05)", minWidth: 210 }}
            initial={{ opacity: 0, x: side === "left" ? -30 : 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.55, delay: 0.08 + index * 0.1 }}
            viewport={{ once: true }}
            whileHover={{ borderColor: `${color}50`, boxShadow: `0 4px 16px rgba(15,23,42,0.1), 0 0 0 1px ${color}20` }}
        >
            <div
                className="flex items-center justify-center w-9 h-9 rounded-lg shrink-0"
                style={{ background: `${color}12`, border: `1px solid ${color}25` }}
            >
                <Icon size={16} style={{ color }} />
            </div>
            <div className="min-w-0">
                <div className="text-[9px] glyph-mono tracking-widest font-bold mb-0.5" style={{ color: `${color}99` }}>
                    {label}
                </div>
                <div className="font-bold text-base text-[#1a1a1a]">{value}</div>
                <div className="text-xs font-medium text-[#737373]">{sub}</div>
            </div>
        </motion.div>
    )
}

// ==========================================
// CORE ORB — Light theme
// ==========================================

function CoreOrb() {
    return (
        <div className="relative flex items-center justify-center" style={{ width: 280, height: 280 }}>
            {/* Ambient glow */}
            <div
                className="absolute rounded-full"
                style={{
                    inset: "5%",
                    background: "radial-gradient(circle, rgba(130,192,164,0.1) 0%, rgba(74,140,112,0.05) 50%, transparent 75%)",
                    filter: "blur(20px)",
                }}
            />

            {/* Outer slow ring */}
            <div className="absolute rounded-full" style={{ inset: 0, border: "1px dashed rgba(130,192,164,0.2)", animation: "orbitalRotate 44s linear infinite" }} />
            <div className="absolute rounded-full" style={{ inset: "8%", border: "1px dashed rgba(74,140,112,0.22)", animation: "orbitalRotateReverse 28s linear infinite" }} />
            <div className="absolute rounded-full" style={{ inset: "18%", border: "1px solid rgba(130,192,164,0.28)", animation: "orbitalRotate 16s linear infinite" }} />

            {/* Pulse rings */}
            {[1, 2, 3].map(i => (
                <motion.div
                    key={i}
                    className="absolute rounded-full pointer-events-none"
                    style={{ inset: `${22 + i * 5}%`, border: `1px solid rgba(130,192,164,${0.3 - i * 0.07})` }}
                    animate={{ opacity: [0.1, 0.5, 0.1], scale: [0.96, 1.04, 0.96] }}
                    transition={{ duration: 2.5 + i * 0.7, repeat: Infinity, delay: i * 0.6 }}
                />
            ))}

            {/* Core dark orb */}
            <motion.div
                className="absolute rounded-full"
                style={{
                    inset: "32%",
                    background: "radial-gradient(circle, #1a1a1a 0%, #1e293b 60%, rgba(130,192,164,0.5) 90%, transparent 100%)",
                    boxShadow: "0 0 30px rgba(130,192,164,0.3), 0 0 60px rgba(130,192,164,0.15)",
                }}
                animate={{ scale: [1, 1.06, 1], opacity: [0.9, 1, 0.9] }}
                transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Inner spark */}
            <div
                className="absolute rounded-full"
                style={{
                    inset: "43%",
                    background: "radial-gradient(circle, rgba(20,184,166,0.9) 0%, rgba(130,192,164,0.7) 50%, transparent 100%)",
                    filter: "blur(2px)",
                }}
            />

            {/* SVG spokes */}
            <svg className="absolute inset-0" width={280} height={280} viewBox="0 0 280 280">
                {[0, 60, 120, 180, 240, 300].map((angle, i) => {
                    const rad = (angle * Math.PI) / 180
                    const cx = 140, cy = 140, r1 = 52, r2 = 126
                    const x1 = Math.round((cx + Math.cos(rad) * r1) * 1000) / 1000
                    const y1 = Math.round((cy + Math.sin(rad) * r1) * 1000) / 1000
                    const x2 = Math.round((cx + Math.cos(rad) * r2) * 1000) / 1000
                    const y2 = Math.round((cy + Math.sin(rad) * r2) * 1000) / 1000
                    return (
                        <motion.line
                            key={angle}
                            x1={x1} y1={y1}
                            x2={x2} y2={y2}
                            stroke={i % 2 === 0 ? "rgba(130,192,164,0.35)" : "rgba(74,140,112,0.28)"}
                            strokeWidth={0.9}
                            strokeDasharray="3 7"
                            animate={{ strokeDashoffset: [21, 0] }}
                            transition={{ duration: 2.8, repeat: Infinity, delay: i * 0.22, ease: "linear" }}
                        />
                    )
                })}
            </svg>

            {/* Center label */}
            <div className="absolute flex flex-col items-center gap-1 z-10">
                <Cpu size={14} style={{ color: "#96cead" }} />
                <div className="glyph-mono text-[8px] font-black tracking-widest text-[#82c0a4]">COGNITIVE</div>
                <div className="glyph-mono text-[8px] tracking-widest text-[#82c0a4]">CORE</div>
            </div>
        </div>
    )
}

// ==========================================
// AI CORE SECTION
// ==========================================

export default function AICoreSection() {
    return (
        <section id="core" className="relative py-28 px-8 overflow-hidden" style={{ background: "#ffffff" }}>
            {/* Top/bottom dividers */}
            <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(130,192,164,0.18), transparent)" }} />
            <div className="absolute bottom-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(74,140,112,0.18), transparent)" }} />

            {/* Soft radial bg */}
            <div className="absolute inset-0 pointer-events-none" style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(130,192,164,0.04) 0%, transparent 60%)" }} />

            <div className="relative z-10 max-w-6xl mx-auto">
                {/* Header */}
                <motion.div
                    className="text-center mb-20"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="text-[10px] glyph-mono tracking-widest text-[#82c0a4] mb-3 font-semibold uppercase">
                        ── AI Cognitive Core ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl leading-tight text-[#1a1a1a]">
                        Neural <span className="text-gradient-blue">Architecture</span>
                    </h2>
                    <p className="mt-4 text-sm text-[#737373] max-w-lg mx-auto leading-relaxed">
                        A persistent cognitive core orchestrating seven specialized agents,
                        four memory tiers, and a multi-LLM routing layer.
                    </p>
                </motion.div>

                {/* Schema: modules | core | modules */}
                <div className="flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-14">
                    {/* LEFT */}
                    <div className="flex flex-col gap-3 w-full lg:w-auto">
                        {LEFT.map((m, i) => <ModuleCard key={m.label} {...m} icon={m.icon} index={i} side="left" />)}
                    </div>

                    {/* CENTER Core */}
                    <motion.div
                        className="shrink-0 flex flex-col items-center gap-6"
                        initial={{ opacity: 0, scale: 0.6 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
                        viewport={{ once: true }}
                    >
                        <CoreOrb />
                        <div className="flex items-center gap-2 px-3 py-1 rounded-full"
                            style={{ background: "rgba(74,140,112,0.08)", border: "1px solid rgba(74,140,112,0.2)" }}>
                            <span className="w-1.5 h-1.5 rounded-full bg-[#4a8c70] animate-blink" />
                            <span className="glyph-mono text-[9px] font-bold tracking-widest text-[#4a8c70]">RUNTIME ACTIVE</span>
                        </div>
                    </motion.div>

                    {/* RIGHT */}
                    <div className="flex flex-col gap-3 w-full lg:w-auto">
                        {RIGHT.map((m, i) => <ModuleCard key={m.label} {...m} icon={m.icon} index={i} side="right" />)}
                    </div>
                </div>
            </div>
        </section>
    )
}

