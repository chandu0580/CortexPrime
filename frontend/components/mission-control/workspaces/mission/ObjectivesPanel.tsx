"use client"

import { useActiveMissions } from "@/hooks"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function ObjectivesPanel() {
  const { data: activeMissions } = useActiveMissions()

  const current = activeMissions?.[0]

  if (!current) {
    return (
      <section>
        <SectionHeader title="Objectives" />
        <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
          <EmptyState
            variant="shell"
            icon={
              <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
              </svg>
            }
            title="No objectives defined"
            description="Mission objectives will be derived from the analyzed intent"
          />
        </div>
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Objectives" />
      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-4 py-3">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#ECFBF4] text-[#38B88A]">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <div>
              <p className="text-[0.82rem] font-semibold text-[#111827]">{current.goal}</p>
              <p className="text-[0.7rem] text-[#6B7280]">Primary mission objective</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
