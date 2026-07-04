"use client"
import { motion } from "framer-motion"
import { useVoiceStore } from "@/store/voiceStore"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import GradientButton from "@/components/ui/GradientButton"

// ==========================================
// WAKE WORD PANEL
// ==========================================

export default function WakeWordPanel() {
    const { wakeWordActive, setWakeWord } = useVoiceStore()

    return (
        <GlassPanel>
            <SectionHeader title="Wake Word" subtitle="Activation phrase detection" />
            <div className="flex flex-col items-center gap-4 py-3">
                <motion.div
                    animate={wakeWordActive ? {
                        boxShadow: ["0 0 0 0 rgba(130,192,164,0.25)", "0 0 0 12px rgba(130,192,164,0)"],
                    } : {}}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="flex h-14 w-14 items-center justify-center rounded-full border border-[#82c0a4]/30 bg-[#f0f7f4]"
                >
                    <div className="h-3.5 w-3.5 rounded-full" style={{ background: wakeWordActive ? "#82c0a4" : "#d1d1d1" }} />
                </motion.div>

                <p className="text-xs text-[#737373]">
                    {wakeWordActive ? '"Hey Cortex" — listening…' : 'Wake word detection off'}
                </p>

                <GradientButton
                    size="sm"
                    onClick={() => setWakeWord(!wakeWordActive)}
                >
                    {wakeWordActive ? "Disable" : "Enable"} Wake Word
                </GradientButton>
            </div>
        </GlassPanel>
    )
}
