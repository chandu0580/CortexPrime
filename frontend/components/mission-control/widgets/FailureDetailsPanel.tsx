"use client"

import { useMissions, useMissionEvents } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function FailureDetailsPanel() {
  const { data: missions } = useMissions()
  const { data: events, isLoading } = useMissionEvents()

  const failedMissions = missions?.filter((m) => m.status === "failed") ?? []
  const failedEvents = events?.filter(
    (ev) => (ev as Record<string, unknown>).status === "error" || (ev as Record<string, unknown>).status === "failed",
  ) ?? []

  if (failedMissions.length === 0 && failedEvents.length === 0) {
    return (
      <section>
        <SectionHeader title="Failure Details" />
        <EmptyState
          variant="shell"
          icon={
            <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          title="No failures detected"
          description="All systems operating normally"
        />
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Failure Details" suffix={<span className="text-[0.7rem] font-medium text-[#EF4444]">{failedMissions.length + failedEvents.length} total</span>} />

      <div className="space-y-2">
        {failedMissions.map((m) => (
          <div key={m.execution_id} className="rounded-[10px] border border-[#FEF2F2] bg-[#FEF2F2] px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-[#EF4444]" />
              <span className="text-[0.8rem] font-semibold text-[#111827]">{m.goal}</span>
            </div>
            <p className="mt-1 text-[0.7rem] text-[#6B7280]">Execution: {m.execution_id}</p>
          </div>
        ))}
        {failedEvents.slice(0, 5).map((ev, i) => {
          const e = ev as Record<string, unknown>
          return (
            <div key={i} className="rounded-[10px] border border-[#FEF2F2] bg-white px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-[#EF4444]" />
                <span className="text-[0.78rem] font-medium text-[#374151]">
                  {String((e as Record<string, unknown>).message ?? (e as Record<string, unknown>).event_type ?? "Unknown error")}
                </span>
              </div>
              {Boolean((e as Record<string, unknown>).agent) && <p className="mt-1 text-[0.68rem] text-[#9CA3AF]">Agent: {String((e as Record<string, unknown>).agent)}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
