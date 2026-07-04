"use client"
import { motion } from "framer-motion"

// ==========================================
// NEURAL CORE — Premium Light Theme
// ==========================================

interface Props { size?: number }

// Orbital rings adapted for light backgrounds
const ORBITAL_RINGS = [
    { size: 200, speed: 14,  color: "rgba(130,192,164,0.3)",   dash: "4 8",  reverse: false, tilt: "rotateX(72deg)" },
    { size: 265, speed: 20,  color: "rgba(74,140,112,0.22)",   dash: "2 12", reverse: true,  tilt: "rotateX(55deg) rotateZ(30deg)" },
    { size: 330, speed: 30,  color: "rgba(130,192,164,0.15)",  dash: "6 10", reverse: false, tilt: "rotateX(80deg) rotateZ(60deg)" },
    { size: 395, speed: 44,  color: "rgba(74,140,112,0.10)",   dash: "3 14", reverse: true,  tilt: "rotateX(62deg) rotateZ(10deg)" },
]

const NODES = [
    { top: "12%", left: "50%", color: "#82c0a4", delay: 0 },
    { top: "50%", left: "95%", color: "#4a8c70", delay: 0.4 },
    { top: "88%", left: "50%", color: "#4a8c70", delay: 0.8 },
    { top: "50%", left: "5%",  color: "#82c0a4", delay: 1.2 },
    { top: "22%", left: "82%", color: "#4a8c70", delay: 0.2 },
    { top: "78%", left: "82%", color: "#82c0a4", delay: 0.6 },
    { top: "22%", left: "18%", color: "#4a8c70", delay: 1.0 },
    { top: "78%", left: "18%", color: "#4a8c70", delay: 1.4 },
]

// Floating capability cards
const CARDS = [
    { label: "REASON",      sub: "Autonomous reasoning engine",   top: "10%",  left: "-28%", delay: 0 },
    { label: "ORCHESTRATE", sub: "Multi-agent coordination",       top: "8%",   right: "-32%", delay: 0.2 },
    { label: "PERCEIVE",    sub: "Real-time data ingestion",       top: "50%",  left: "-35%", delay: 0.4 },
    { label: "MEMORIZE",    sub: "Persistent cognitive memory",    top: "50%",  right: "-38%", delay: 0.6 },
    { label: "ADAPT",       sub: "Continuous learning & optimization", bottom: "8%", right: "-30%", delay: 0.8 },
]

export default function NeuralCore({ size = 440 }: Props) {
    const half = size / 2

    return (
        <div className="relative select-none" style={{ width: size, height: size }}>

            {/* ── Soft ambient glow ── */}
            <div
                className="absolute rounded-full pointer-events-none"
                style={{
                    inset: "10%",
                    background: "radial-gradient(circle, rgba(130,192,164,0.12) 0%, rgba(74,140,112,0.06) 45%, transparent 70%)",
                    filter: "blur(24px)",
                }}
            />

            {/* ── Orbital rings ── */}
            {ORBITAL_RINGS.map((ring, i) => (
                <div
                    key={i}
                    className="absolute rounded-full pointer-events-none"
                    style={{
                        width:  ring.size,
                        height: ring.size,
                        top:    half - ring.size / 2,
                        left:   half - ring.size / 2,
                        transform: ring.tilt,
                        animation: `${ring.reverse ? "orbitalRotateReverse" : "orbitalRotate"} ${ring.speed}s linear infinite`,
                        border: `1px dashed ${ring.color}`,
                    }}
                />
            ))}

            {/* ── Pulse rings ── */}
            {[1, 2, 3].map(i => (
                <motion.div
                    key={`pulse-${i}`}
                    className="absolute rounded-full pointer-events-none"
                    style={{
                        inset: `${20 + i * 8}%`,
                        border: `1px solid rgba(130,192,164,${0.25 - i * 0.06})`,
                    }}
                    animate={{ opacity: [0.15, 0.55, 0.15], scale: [0.97, 1.03, 0.97] }}
                    transition={{ duration: 2.8 + i * 0.8, repeat: Infinity, delay: i * 0.5 }}
                />
            ))}

            {/* ── Core dark hexagonal orb ── */}
            <motion.div
                className="absolute rounded-full pointer-events-none"
                style={{
                    inset: "35%",
                    background: "radial-gradient(circle, #1a1a1a 0%, #1e293b 50%, rgba(130,192,164,0.4) 80%, transparent 100%)",
                    boxShadow: "0 0 40px rgba(130,192,164,0.25), 0 0 80px rgba(130,192,164,0.12)",
                }}
                animate={{ scale: [1, 1.05, 1], opacity: [0.9, 1, 0.9] }}
                transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* ── Inner core spark ── */}
            <div
                className="absolute rounded-full pointer-events-none"
                style={{
                    inset: "44%",
                    background: "radial-gradient(circle, rgba(20,184,166,0.9) 0%, rgba(130,192,164,0.6) 50%, transparent 100%)",
                    filter: "blur(3px)",
                }}
            />

            {/* ── Orbiting nodes ── */}
            {NODES.map((node, i) => (
                <motion.div
                    key={`node-${i}`}
                    className="absolute rounded-full pointer-events-none"
                    style={{
                        width: 7,
                        height: 7,
                        top:  node.top,
                        left: node.left,
                        transform: "translate(-50%, -50%)",
                        background: node.color,
                        boxShadow: `0 0 10px ${node.color}60`,
                    }}
                    animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.5, 0.8] }}
                    transition={{ duration: 2.2, repeat: Infinity, delay: node.delay }}
                />
            ))}

            {/* ── Floating capability cards ── */}
            {CARDS.map((card, i) => (
                <motion.div
                    key={card.label}
                    className="absolute flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl pointer-events-none"
                    style={{
                        top:    card.top,
                        left:   (card as any).left,
                        right:  (card as any).right,
                        bottom: (card as any).bottom,
                        background: "rgba(255,255,255,0.92)",
                        backdropFilter: "blur(12px)",
                        border: "1px solid rgba(226,232,240,0.9)",
                        boxShadow: "0 4px 16px rgba(15,23,42,0.08)",
                        whiteSpace: "nowrap",
                        minWidth: 160,
                    }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{
                        opacity: 1,
                        y: [0, -5, 0],
                    }}
                    transition={{
                        opacity: { delay: card.delay + 0.6, duration: 0.5 },
                        y: { duration: 3.5 + i * 0.4, repeat: Infinity, ease: "easeInOut", delay: card.delay },
                    }}
                >
                    <div
                        className="w-6 h-6 rounded-md flex items-center justify-center shrink-0"
                        style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)" }}
                    >
                        <div className="w-2 h-2 rounded-full bg-white opacity-90" />
                    </div>
                    <div>
                        <div className="text-[10px] font-black tracking-widest text-[#1a1a1a] uppercase">{card.label}</div>
                        <div className="text-[9px] text-[#737373] leading-tight mt-0.5">{card.sub}</div>
                    </div>
                </motion.div>
            ))}
        </div>
    )
}

