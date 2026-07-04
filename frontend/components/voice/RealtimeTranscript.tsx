"use client"
import { motion, AnimatePresence } from "framer-motion"
import { useVoiceStore } from "@/store/voiceStore"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import { cn } from "@/utils/cn"

// ==========================================
// REALTIME TRANSCRIPT
// ==========================================

export default function RealtimeTranscript() {
    const { transcripts } = useVoiceStore()

    return (
        <GlassPanel>
            <SectionHeader title="Live Transcript" subtitle="Realtime voice-to-text" />
            <div className="cortex-scroll space-y-2 max-h-64 overflow-y-auto">
                <AnimatePresence initial={false}>
                    {transcripts.slice(-20).map((t) => (
                        <motion.div
                            key={t.id}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={cn(
                                "flex gap-2 rounded-lg px-3 py-2 text-sm",
                                t.speaker === "user"
                                    ? "border border-blue-500/20 bg-blue-500/5 justify-end"
                                    : "border border-[#82c0a4]/20 bg-[#82c0a4]/5"
                            )}
                        >
                            <span className={t.speaker === "user" ? "text-[#96cead]" : "text-[#96cead]"}>
                                {t.text}
                            </span>
                            {!t.isFinal && (
                                <span className="animate-stream-cursor inline-block w-0.5 h-3 bg-current" />
                            )}
                        </motion.div>
                    ))}
                </AnimatePresence>
                {transcripts.length === 0 && (
                    <p className="text-center text-sm text-[#737373] py-6">Awaiting voice input…</p>
                )}
            </div>
        </GlassPanel>
    )
}
