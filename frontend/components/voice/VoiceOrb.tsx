"use client"
import { motion } from "framer-motion"
import { useVoiceStore } from "@/store/voiceStore"
import { cn } from "@/utils/cn"

// ==========================================
// VOICE ORB
// ==========================================

export default function VoiceOrb() {
    const { status } = useVoiceStore()
    const isActive = status === "listening" || status === "speaking"

    return (
        <div className="flex flex-col items-center gap-3">
            <div className="relative">
                {/* Ripples */}
                {isActive && [1, 2, 3].map((i) => (
                    <motion.div
                        key={i}
                        className="absolute inset-0 rounded-full border border-[#82c0a4]/40"
                        animate={{ scale: [1, 1 + i * 0.4], opacity: [0.5, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.4, ease: "easeOut" }}
                    />
                ))}

                {/* Core orb */}
                <motion.div
                    animate={isActive ? {
                        boxShadow: [
                            "0 0 20px rgba(130,192,164,0.3)",
                            "0 0 50px rgba(130,192,164,0.5)",
                            "0 0 20px rgba(130,192,164,0.3)",
                        ],
                    } : {}}
                    transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
                    className={cn(
                        "relative flex h-20 w-20 items-center justify-center rounded-full",
                        "border-2 transition-colors duration-300",
                        isActive
                            ? "border-[#82c0a4]/80 bg-gradient-to-br from-[#82c0a4]/20 to-[#4a8c70]/15"
                            : "border-[#dceee4] bg-[#f0f7f4]"
                    )}
                >
                    <span className="text-2xl">
                        {status === "listening"  ? "🎤" :
                         status === "speaking"   ? "🔊" :
                         status === "processing" ? "⚡" : "🤫"}
                    </span>
                </motion.div>
            </div>

            <span className={cn(
                "text-xs font-medium capitalize",
                isActive ? "text-[#82c0a4]" : "text-[#a3a3a3]"
            )}>
                {status}
            </span>
        </div>
    )
}
