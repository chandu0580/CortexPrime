"use client"
import { motion } from "framer-motion"
import { useVoiceStore } from "@/store/voiceStore"

// ==========================================
// VOICE WAVEFORM
// ==========================================

const BARS = 32

export default function VoiceWaveform() {
    const { status } = useVoiceStore()
    const active = status === "listening" || status === "speaking"

    return (
        <div className="flex items-center justify-center gap-0.5 h-12">
            {Array.from({ length: BARS }).map((_, i) => (
                <motion.div
                    key={i}
                    className="w-1 rounded-full bg-gradient-to-t from-[#82c0a4] to-[#4a8c70]"
                    animate={active ? {
                        scaleY: [
                            0.2,
                            0.2 + Math.random() * 0.8,
                            0.2,
                        ],
                    } : { scaleY: 0.1 }}
                    transition={{
                        duration: 0.5 + Math.random() * 0.5,
                        repeat: Infinity,
                        delay: i * 0.03,
                        ease: "easeInOut",
                    }}
                    style={{ height: 40, originY: "bottom" }}
                />
            ))}
        </div>
    )
}
