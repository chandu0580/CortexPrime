import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"

export function DependencyGraph() {
  return (
    <section>
      <SectionHeader title="Mission Dependency Graph" />

      <EmptyState
        variant="shell"
        icon={
          <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        }
        title="No dependencies available"
        description="Dependencies will be resolved during mission planning"
      />
    </section>
  )
}
