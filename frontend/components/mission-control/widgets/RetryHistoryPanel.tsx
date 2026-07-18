"use client"

import { useMemo } from "react"
import { useMissions, useMissionEvents } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function RetryHistoryPanel() {
  const { data: missions } = useMissions()
  const { data: events } = useMissionEvents()

  const retries = useMemo(() => {
    if (!events || !Array.isArray(events)) return []
    return events
      .filter(
        (ev) =>
          String((ev as Record<string, unknown>).event_type ?? "").toLowerCase().includes("retry") ||
          String((ev as Record<string, unknown>).message ?? "").toLowerCase().includes("retry") ||
          String((ev as Record<string, unknown>).status ?? "").toLowerCase().includes("retry"),
      )
      .slice(0, 10)
  }, [events])

  const failedCount = missions?.filter((m) => m.status === "failed").length ?? 0
  const completedCount = missions?.filter((m) => m.status === "completed").length ?? 0

  if (retries.length === 0 && failedCount === 0) {
    return (
      <section>
        <SectionHeader title="Retry History" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
            </svg>
          }
          title="No retries recorded"
          description="Retries will be logged when missions are re-attempted after failures"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader
        title="Retry History"
        suffix={<span className="text-[0.7rem] text-[#B0B7C3]">{retries.length + failedCount} events</span>}
      />

      <div className="space-y-2">
        {failedCount > 0 && (
          <div className="rounded-[10px] border border-[#FEF2F2] bg-[#FEF2F2] px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-[0.8rem] font-medium text-[#111827]">Failed missions requiring retry</span>
              <span className="text-[0.9rem] font-bold text-[#EF4444]">{failedCount}</span>
            </div>
            <p className="mt-1 text-[0.7rem] text-[#6B7280]">{completedCount} completed successfully</p>
          </div>
        )}
        {retries.map((ev, i) => {
          const e = ev as Record<string, unknown>
          return (
            <div key={i} className="flex items-center justify-between rounded-[8px] border border-[#E8EDF3] px-4 py-2.5">
              <div className="flex items-center gap-2">
                <svg className="h-3.5 w-3.5 text-[#F59E0B]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
                <span className="text-[0.78rem] text-[#374151]">{String((e as Record<string, unknown>).message ?? (e as Record<string, unknown>).event_type)}</span>
              </div>
              {Boolean((e as Record<string, unknown>).agent) && <span className="text-[0.68rem] text-[#9CA3AF]">{String((e as Record<string, unknown>).agent)}</span>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
