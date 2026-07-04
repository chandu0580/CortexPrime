"use client"
import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Brain } from "lucide-react"

const PHASES = [
    "Orchestrating agents",
    "Analyzing objective",
    "Planning execution",
    "Gathering intelligence",
    "Synthesizing response",
]

export default function TypingIndicator() {
    const [phaseIdx, setPhaseIdx] = useState(0)

    useEffect(() => {
        const t = setInterval(() => {
            setPhaseIdx((i) => (i + 1) % PHASES.length)
        }, 2000)
        return () => clearInterval(t)
    }, [])

    return (
        <div className="flex items-start gap-3">
            <div className="relative mt-0.5 shrink-0">
                <div
                    className="flex h-8 w-8 items-center justify-center rounded-xl text-white shadow-md"
                    style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)" }}
                >
                    <Brain size={14} />
                </div>
                <motion.div
                    className="absolute inset-0 rounded-xl"
                    style={{ border: "2px solid rgba(130,192,164,0.5)" }}
                    animate={{ scale: [1, 1.6], opacity: [0.7, 0] }}
                    transition={{ duration: 1.0, repeat: Infinity }}
                />
            </div>

            <div
                className="rounded-2xl rounded-bl-sm px-4 py-3 text-white"
                style={{
                    background: "#82c0a4",
                    border: "1px solid rgba(74,140,112,0.2)",
                    boxShadow: "0 2px 8px rgba(130,192,164,0.18)",
                }}
            >
                <div className="mb-1 text-[10px] font-bold uppercase tracking-widest text-white/70">
                    CortexPrime
                </div>

                <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2.5">
                        <AnimatePresence mode="wait">
                            <motion.span
                                key={phaseIdx}
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                transition={{ duration: 0.25 }}
                                className="text-xs font-medium text-white"
                            >
                                {PHASES[phaseIdx]}
                            </motion.span>
                        </AnimatePresence>

                        <div className="flex gap-1">
                            {[0, 1, 2].map((i) => (
                                <motion.span
                                    key={i}
                                    className="h-1.5 w-1.5 rounded-full bg-white/80"
                                    animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
                                    transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.18 }}
                                />
                            ))}
                        </div>
                    </div>

                    <div className="h-0.5 w-44 overflow-hidden rounded-full bg-white/20">
                        <motion.div
                            className="h-full rounded-full"
                            style={{ background: "linear-gradient(90deg, #ffffff, rgba(255,255,255,0.5), #ffffff)" }}
                            animate={{ x: ["-110%", "110%"] }}
                            transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}
