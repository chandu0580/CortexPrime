"use client"
import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { runtimeService } from "@/services/runtime"
import { formatRelativeTime } from "@/lib/formatting"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import StatusPill from "@/components/ui/StatusPill"
import { POLL_INTERVAL_MS } from "@/lib/constants"
import type { RuntimeEvent } from "@/types/runtime"

// ==========================================
// RUNTIME EVENTS
// ==========================================

export default function RuntimeEvents() {
    const [events, setEvents] = useState<RuntimeEvent[]>([])

    useEffect(() => {
        const poll = async () => {
            try {
                const r = await runtimeService.getEvents() as { events: RuntimeEvent[] }
                setEvents((r.events ?? []).slice(0, 25))
            } catch {}
        }
        poll()
        const t = setInterval(poll, POLL_INTERVAL_MS)
        return () => clearInterval(t)
    }, [])

    return (
        <GlassPanel>
            <SectionHeader title="Runtime Events" subtitle={`${events.length} recent events`} />
            <div className="cortex-scroll space-y-1.5 overflow-y-auto max-h-72">
                {events.map((evt, i) => (
                    <motion.div
                        key={evt.id ?? i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex items-center gap-2 rounded-lg border border-[#e8f5ee] bg-[#f0f7f4] px-3 py-2"
                    >
                        <StatusPill label={evt.type} variant="info" />
                        <span className="flex-1 text-sm text-[#4a4a4a] font-medium truncate">{evt.message}</span>
                        <span className="shrink-0 text-xs text-[#737373] tabular-nums">
                            {formatRelativeTime(evt.timestamp)}
                        </span>
                    </motion.div>
                ))}
                {events.length === 0 && (
                    <p className="text-center text-sm text-[#737373] py-6">No events yet</p>
                )}
            </div>
        </GlassPanel>
    )
}
