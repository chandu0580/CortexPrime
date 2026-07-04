"use client"
import { Monitor, Mouse, Keyboard } from "lucide-react"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import RuntimeBadge from "@/components/ui/RuntimeBadge"

// ==========================================
// DESKTOP TELEMETRY
// ==========================================

const tools = [
    { label: "Screen Capture",  icon: Monitor,  status: "active" as const },
    { label: "Mouse Control",   icon: Mouse,    status: "active" as const },
    { label: "Keyboard Input",  icon: Keyboard, status: "active" as const },
]

export default function DesktopTelemetry() {
    return (
        <GlassPanel>
            <SectionHeader title="Desktop Telemetry" subtitle="Hardware interaction status" />
            <div className="space-y-2">
                {tools.map(({ label, icon: Icon, status }) => (
                    <div key={label} className="flex items-center gap-3 rounded-lg border border-[#dceee4] bg-[#f0f7f4] px-3 py-2.5">
                        <Icon size={14} className="shrink-0" style={{ color: "#a3a3a3" }} />
                        <span className="flex-1 text-xs text-[#4a4a4a]">{label}</span>
                        <RuntimeBadge label={status} status={status} />
                    </div>
                ))}
            </div>
        </GlassPanel>
    )
}
