"use client"
import { useVoiceStore } from "@/store/voiceStore"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import RuntimeBadge from "@/components/ui/RuntimeBadge"

// ==========================================
// VOICE TELEMETRY
// ==========================================

export default function VoiceTelemetry() {
    const { status, activeProfile, wakeWordActive, transcripts } = useVoiceStore()

    const metrics = [
        { label: "Status",       value: status,         badge: true },
        { label: "Profile",      value: activeProfile,  badge: false },
        { label: "Wake Word",    value: wakeWordActive ? "Active" : "Inactive", badge: true },
        { label: "Transcripts",  value: transcripts.length, badge: false },
    ]

    return (
        <GlassPanel>
            <SectionHeader title="Voice Telemetry" />
            <div className="grid grid-cols-2 gap-2">
                {metrics.map((m) => (
                    <div key={m.label} className="rounded-lg border border-[#dceee4] bg-[#f0f7f4] px-3 py-2">
                        <p className="text-xs font-semibold text-[#737373] mb-1">{m.label}</p>
                        {m.badge ? (
                            <RuntimeBadge
                                label={String(m.value)}
                                status={
                                    m.value === "Active" || m.value === "listening" || m.value === "speaking"
                                        ? "active"
                                        : m.value === "processing"
                                        ? "degraded"
                                        : "idle"
                                }
                            />
                        ) : (
                            <p className="text-sm font-bold text-slate-200">{m.value}</p>
                        )}
                    </div>
                ))}
            </div>
        </GlassPanel>
    )
}
