import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function DecisionQueue() {
  return (
    <section>
      <SectionHeader title="Decision Queue" />

      <EmptyState
        variant="shell"
        icon={
          <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        }
        title="No decisions requiring attention"
        description="Decisions will appear when missions require executive input"
      />
    </section>
  )
}
