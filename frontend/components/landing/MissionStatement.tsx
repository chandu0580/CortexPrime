"use client"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"

// ==========================================
// MISSION STATEMENT — Premium Light
// ==========================================

export default function MissionStatement() {
    return (
        <section id="mission" className="relative py-32 px-8 overflow-hidden" style={{ background: "#f0f7f4" }}>
            {/* Dividers */}
            <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(130,192,164,0.2), transparent)" }} />
            <div className="absolute bottom-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(74,140,112,0.2), transparent)" }} />

            {/* Subtle radial */}
            <div className="absolute inset-0 pointer-events-none" style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(130,192,164,0.05) 0%, transparent 60%)" }} />

            <div className="relative z-10 max-w-3xl mx-auto text-center">
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8 }}
                    viewport={{ once: true }}
                >
                    <div className="text-[10px] glyph-mono tracking-widest text-[#82c0a4] mb-8 font-semibold uppercase">
                        ── Mission Directive ──
                    </div>

                    <h2
                        className="font-black leading-tight text-[#1a1a1a] mb-8"
                        style={{ fontSize: "clamp(1.8rem,4.5vw,3.5rem)" }}
                    >
                        The future of AI is{" "}
                        <span className="text-gradient-blue">autonomous</span>{" "}
                        and{" "}
                        <span className="text-gradient-blue">cognitive.</span>
                    </h2>

                    <p className="text-base font-medium text-[#4a4a4a] leading-relaxed mb-5 max-w-2xl mx-auto">
                        CortexPrime is not a chatbot. It is a complete cognitive operating system �
                        an elite infrastructure that thinks, plans, researches, critiques, and executes
                        with the precision of a mission-critical system.
                    </p>
                    <p className="text-base text-[#737373] leading-relaxed mb-12 max-w-xl mx-auto">
                        Built for operators who demand more than a language model wrapper.
                        Designed for the era when AI systems run autonomously, persistently, and intelligently.
                    </p>

                    <Link href="/login">
                        <motion.button
                            className="group inline-flex items-center gap-3 px-8 py-4 text-sm font-semibold text-white rounded-xl"
                            style={{
                                background: "linear-gradient(135deg, #82c0a4, #4a8c70)",
                                boxShadow: "0 8px 24px rgba(130,192,164,0.3)",
                            }}
                            whileHover={{ boxShadow: "0 12px 32px rgba(130,192,164,0.4)", y: -2 }}
                            whileTap={{ scale: 0.97 }}
                        >
                            Access the Runtime
                            <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                        </motion.button>
                    </Link>
                </motion.div>
            </div>
        </section>
    )
}


