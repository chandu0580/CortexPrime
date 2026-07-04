"use client"
import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { runtimeService } from "@/services/runtime"
import { formatRelativeTime } from "@/lib/formatting"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import StatusPill from "@/components/ui/StatusPill"
import MissionTimeline from "@/components/chat/MissionTimeline"
import { POLL_INTERVAL_MS } from "@/lib/constants"
import type { Mission } from "@/types/runtime"

// ==========================================
// RUNTIME HEALTH
// ==========================================

export default function RuntimeHealth() {
    const [missions, setMissions] = useState<Mission[]>([])

    useEffect(() => {
        const poll = async () => {
            try {
                const [active, completed] = await Promise.allSettled([
                    runtimeService.getActiveMissions(),
                    runtimeService.getCompletedMissions(),
                ])
                const list: Mission[] = []
                if (active.status === "fulfilled")    list.push(...(active.value.active_missions ?? []))
                if (completed.status === "fulfilled") list.push(...(completed.value.completed_missions ?? []))
                setMissions(list.slice(0, 20))
            } catch {}
        }
        poll()
        const t = setInterval(poll, POLL_INTERVAL_MS)
        return () => clearInterval(t)
    }, [])

    return (
        <GlassPanel>
            <SectionHeader title="Mission Health" subtitle={`${missions.length} missions tracked`} />
            <MissionTimeline missions={missions} />
        </GlassPanel>
    )
}
