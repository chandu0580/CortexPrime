"use client"

import { useMemo } from "react"
import { useMissions, useMissionReplay } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"
import type { MissionTimelineEvent } from "@/services/mission-control/missions"

export function TokenUsagePanel() {
  const { data: missions } = useMissions()
  const latestMission = missions?.[0]
  const execId = latestMission?.execution_id ?? null

  const { data: replay } = useMissionReplay(execId)

  const totalTokens = useMemo(() => {
    if (!replay || !Array.isArray(replay)) return null
    let sum = 0
    for (const ev of replay) {
      const tu = (ev as unknown as Record<string, unknown>).token_usage
      if (tu && typeof tu === "object") {
        sum += Number((tu as Record<string, unknown>).total_tokens ?? 0)
        sum += Number((tu as Record<string, unknown>).prompt_tokens ?? 0)
        sum += Number((tu as Record<string, unknown>).completion_tokens ?? 0)
      }
    }
    return sum
  }, [replay])

  const completionTokens = useMemo(() => {
    if (!replay || !Array.isArray(replay)) return null
    let sum = 0
    for (const ev of replay) {
      const tu = (ev as unknown as Record<string, unknown>).token_usage
      if (tu && typeof tu === "object") {
        sum += Number((tu as Record<string, unknown>).completion_tokens ?? 0)
      }
    }
    return sum
  }, [replay])

  return (
    <section>
      <SectionHeader title="Token Usage" suffix={<span className="text-[0.7rem] text-[#B0B7C3]">Latest mission</span>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <InfoCard label="Total Tokens">
          <p className="text-[1.1rem] font-bold text-[#111827]">
            {totalTokens != null ? totalTokens.toLocaleString() : execId ? "Loading..." : "N/A"}
          </p>
        </InfoCard>
        <InfoCard label="Completion Tokens">
          <p className="text-[1.1rem] font-bold text-[#111827]">
            {completionTokens != null ? completionTokens.toLocaleString() : execId ? "Loading..." : "N/A"}
          </p>
        </InfoCard>
        <InfoCard label="Mission">
          <p className="text-[0.78rem] font-medium text-[#111827] truncate">
            {latestMission?.goal ?? "No active mission"}
          </p>
        </InfoCard>
      </div>
    </section>
  )
}
